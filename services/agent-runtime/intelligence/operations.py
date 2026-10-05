from __future__ import annotations

import math
import re
from collections import Counter

from .common import canonical, digest, integer, number, numeric_values, percentile, rows, text, timestamp, unique_ids
from .retrieval import answerability, detect_conflicts, freshness, pack_context, rank_passages, redact_text, validate_citations
from .security import injection_scan


def health_summary(p: dict) -> dict:
    services = rows(p, "services")
    unique_ids(services)
    now = timestamp(p.get("now"), "now")
    ttl = number(p.get("ttl_seconds", 60), "ttl_seconds", 0)
    blockers = []
    optional_failures = []
    for service in services:
        if not isinstance(service.get("required"), bool) or not isinstance(service.get("healthy"), bool):
            raise ValueError("service_flags_must_be_boolean")
        age = (now - timestamp(service.get("observed_at"), "observed_at")).total_seconds()
        healthy = service["healthy"] and 0 <= age <= ttl
        if not healthy:
            (blockers if service["required"] else optional_failures).append(service["id"])
    if not any(x["required"] for x in services):
        raise ValueError("required_service_needed")
    return {"status": "degraded" if blockers else "ok", "blockers": blockers, "optional_failures": optional_failures, "based_on_supplied_observations": True, "services_probed": False}


def slo_report(p: dict) -> dict:
    total = integer(p.get("total"), "total", 1, 10**12)
    successful = integer(p.get("successful"), "successful", 0, total)
    target = number(p.get("target", 0.99), "target", 0)
    if not 0 < target <= 1:
        raise ValueError("target_must_be_in_zero_one_interval")
    failures = total - successful
    budget = total * (1 - target)
    return {"success_ratio": successful / total, "target_met": successful / total >= target, "allowed_failures": budget, "observed_failures": failures, "remaining_error_budget": budget - failures, "budget_consumed_ratio": failures / budget if budget else None}


def latency_report(p: dict) -> dict:
    values = numeric_values(p, nonnegative=True)
    return {"count": len(values), "p50": percentile(values, 0.5), "p90": percentile(values, 0.9), "p95": percentile(values, 0.95), "p99": percentile(values, 0.99), "max": max(values), "unit": "milliseconds", "method": "linear_interpolation"}


def cluster_errors(p: dict) -> dict:
    errors = rows(p, "errors")
    counts = Counter()
    labels = {}
    for item in errors:
        value = redact_text({"text": text(item.get("message"), "message")})["text"]
        value = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", "<id>", value, flags=re.I)
        value = re.sub(r"\b\d+\b", "<number>", value)
        signature = " ".join(value.casefold().split())
        key = digest(signature)
        counts[key] += 1
        labels[key] = signature
    return {"clusters": [{"signature_sha256": key, "summary": labels[key], "count": count} for key, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))], "heuristic_grouping": True, "incidents_created": False}


def capacity_estimate(p: dict) -> dict:
    rate = number(p.get("requests_per_second"), "requests_per_second", 0)
    latency = number(p.get("service_time_seconds"), "service_time_seconds", 0)
    slots = integer(p.get("slots_per_instance"), "slots_per_instance", 1, 100000)
    target = number(p.get("target_utilization", 0.7), "target_utilization", 0)
    if not 0 < target <= 1:
        raise ValueError("target_utilization_out_of_range")
    concurrent = rate * latency
    instances = math.ceil(concurrent / (slots * target))
    return {"estimated_concurrency": concurrent, "estimated_instances": instances, "method": "little_law_steady_state", "burst_capacity_included": False, "instances_provisioned": False}


def regression_report(p: dict) -> dict:
    metrics = rows(p, "metrics")
    unique_ids(metrics)
    report = []
    for item in metrics:
        baseline = number(item.get("baseline"), "baseline")
        current = number(item.get("current"), "current")
        tolerance = number(item.get("absolute_tolerance", 0), "absolute_tolerance", 0)
        direction = item.get("direction")
        if direction not in {"higher", "lower"}:
            raise ValueError("metric_direction_required")
        degradation = baseline - current if direction == "higher" else current - baseline
        report.append({"id": item["id"], "delta": current - baseline, "relative_delta": (current - baseline) / abs(baseline) if baseline else None, "regressed": degradation > tolerance})
    return {"metrics": report, "passed": not any(x["regressed"] for x in report), "measurement_performed": False}


def evaluation_scorecard(p: dict) -> dict:
    cases = rows(p, "cases")
    unique_ids(cases)
    results = []
    for item in cases:
        if "expected" not in item or "actual" not in item or not isinstance(item.get("critical"), bool):
            raise ValueError("expected_actual_and_critical_required")
        results.append({"id": item["id"], "passed": canonical(item["expected"]) == canonical(item["actual"]), "critical": item["critical"]})
    passed = sum(x["passed"] for x in results)
    return {"cases": results, "pass_ratio": passed / len(results), "critical_failures": [x["id"] for x in results if x["critical"] and not x["passed"]], "results_independently_verified": False}


REQUIRED_CHECKS = ("compilation", "regressions", "milestones", "api", "web", "security")


def release_gate(p: dict) -> dict:
    commit = text(p.get("commit"), "commit")
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("full_commit_sha_required")
    checks = rows(p, "checks", allow_empty=True)
    unique_ids(checks)
    now = timestamp(p.get("now"), "now")
    ttl = number(p.get("ttl_seconds", 86400), "ttl_seconds", 0)
    index = {x["id"]: x for x in checks}
    blockers = []
    for identifier in REQUIRED_CHECKS:
        check = index.get(identifier)
        if check is None:
            blockers.append({"id": identifier, "reason": "missing_check"})
            continue
        age = (now - timestamp(check.get("observed_at"), "observed_at")).total_seconds()
        if check.get("passed") is not True or check.get("commit") != commit or not 0 <= age <= ttl or check.get("evidence_kind") != "test_run":
            blockers.append({"id": identifier, "reason": "failed_stale_wrong_commit_or_unmeasured"})
    if p.get("protected_invariants_hold") is not True:
        blockers.append({"id": "protected_invariants", "reason": "invariants_not_confirmed"})
    return {"eligible_for_release_review": not blockers, "blockers": blockers, "evidence_authenticated": False, "release_certified": False, "deployed": False}


def compatibility_report(p: dict) -> dict:
    before = rows(p, "before", allow_empty=True)
    after = rows(p, "after", allow_empty=True)
    unique_ids(before)
    unique_ids(after)
    old, new = {x["id"]: x for x in before}, {x["id"]: x for x in after}
    for item in before + after:
        for field in ("required_inputs", "output_fields"):
            value = item.get(field)
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise ValueError("contract_field_lists_required")
        text(item.get("method"), "method")
    breaks = []
    for identifier, item in old.items():
        replacement = new.get(identifier)
        if replacement is None:
            breaks.append({"id": identifier, "reason": "endpoint_removed"})
            continue
        if item["method"] != replacement["method"]:
            breaks.append({"id": identifier, "reason": "method_changed"})
        if set(replacement["required_inputs"]) - set(item["required_inputs"]):
            breaks.append({"id": identifier, "reason": "new_required_input"})
        if set(item["output_fields"]) - set(replacement["output_fields"]):
            breaks.append({"id": identifier, "reason": "output_removed"})
    return {"structurally_compatible": not breaks, "breaking_changes": breaks, "added_endpoints": sorted(new.keys() - old.keys()), "semantic_compatibility_tested": False}


def evidence_pipeline(p: dict) -> dict:
    ranked = rank_passages(p)
    now = text(p.get("now"), "now")
    ttl = number(p.get("ttl_seconds", 86400), "ttl_seconds", 0)
    accepted, quarantined = [], []
    for item in ranked["passages"]:
        scan = injection_scan({"text": item["text"]})
        observed = freshness({"now": now, "ttl_seconds": ttl, "sources": [{"id": item["id"], "observed_at": item.get("observed_at")}]})
        if scan["review_required"] or not observed["all_fresh"]:
            quarantined.append({"id": item["id"], "reason": "instruction_risk" if scan["review_required"] else "stale_or_future_source"})
        else:
            accepted.append({**item, "text": redact_text({"text": item["text"]})["text"]})
    packed = pack_context({**p, "passages": accepted})
    packed_ids = set(packed["citation_ids"])
    selected = [x for x in accepted if x["id"] in packed_ids]
    analysis = answerability({**p, "passages": selected})
    conflicts = detect_conflicts({"claims": p["claims"]}) if p.get("claims") else {"conflicts": [], "conflict_free": True}
    citations = validate_citations({**p, "passages": selected}) if p.get("citations") is not None else None
    citation_ok = citations is None or citations["all_valid"]
    available = analysis["answerable"] and conflicts["conflict_free"] and citation_ok
    boundary = "EVIDENCE_AVAILABLE" if available else "CONFLICT" if not conflicts["conflict_free"] else "DATA_REQUIRED"
    return {"boundary": boundary, "context": packed["context"] if available else "", "citation_ids": packed["citation_ids"] if available else [], "quarantined_sources": quarantined, "answerability": analysis, "citation_validation": citations, "conflicts": conflicts["conflicts"], "answer_generated": False, "source_truth_verified": False, "persistent_change_applied": False}


CAPABILITIES = (
    (91, "health_summary", health_summary), (92, "slo_report", slo_report),
    (93, "latency_report", latency_report), (94, "cluster_errors", cluster_errors),
    (95, "capacity_estimate", capacity_estimate), (96, "regression_report", regression_report),
    (97, "evaluation_scorecard", evaluation_scorecard), (98, "release_gate", release_gate),
    (99, "compatibility_report", compatibility_report), (100, "evidence_pipeline", evidence_pipeline),
)
