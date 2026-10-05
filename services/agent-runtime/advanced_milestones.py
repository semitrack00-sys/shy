from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AdvancedBoundary(str, Enum):
    READY = "READY"
    INVALID_INPUT = "INVALID_INPUT"
    DATA_REQUIRED = "DATA_REQUIRED"
    PROTECTED_TARGET = "PROTECTED_TARGET"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class AdvancedResult:
    capability: str
    boundary: AdvancedBoundary
    reason: str
    payload: dict[str, object]
    side_effect_performed: bool


_PROTECTED_RECOVERY_MARKERS = (
    "security policy",
    "credentials",
    "password",
    "private key",
    "authentication",
    "authorization",
    "permission store",
)


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _recovery_rollback(payload: Mapping[str, object]) -> AdvancedResult:
    target = str(payload.get("target_checkpoint") or "").strip()
    raw_checkpoints = payload.get("checkpoints") or []

    if not isinstance(raw_checkpoints, list):
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.INVALID_INPUT,
            "checkpoints_must_be_a_list",
            {},
            False,
        )

    checkpoints: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in raw_checkpoints[:64]:
        if not isinstance(raw, dict):
            continue
        checkpoint_id = str(raw.get("checkpoint_id") or "").strip()
        if not checkpoint_id or checkpoint_id in seen:
            return AdvancedResult(
                "recovery_rollback",
                AdvancedBoundary.INVALID_INPUT,
                "checkpoint_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(checkpoint_id)
        checkpoints.append(
            {
                "checkpoint_id": checkpoint_id,
                "verified": bool(raw.get("verified", False)),
                "description": str(raw.get("description") or "").strip()[:500],
            }
        )

    if not target:
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.DATA_REQUIRED,
            "target_checkpoint_required",
            {"checkpoint_count": len(checkpoints)},
            False,
        )

    protected_text = _norm(payload.get("target_resource")) + " " + _norm(payload.get("objective"))
    if any(marker in protected_text for marker in _PROTECTED_RECOVERY_MARKERS):
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.PROTECTED_TARGET,
            "protected_security_or_credential_target",
            {"target_checkpoint": target},
            False,
        )

    selected = next((item for item in checkpoints if item["checkpoint_id"] == target), None)
    if selected is None:
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.DATA_REQUIRED,
            "target_checkpoint_not_found",
            {"target_checkpoint": target, "checkpoint_count": len(checkpoints)},
            False,
        )

    if not bool(selected["verified"]):
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.CONFLICT,
            "verified_checkpoint_required",
            {"target_checkpoint": target, "verified": False},
            False,
        )

    return AdvancedResult(
        "recovery_rollback",
        AdvancedBoundary.READY,
        "rollback_plan_ready",
        {
            "target_checkpoint": target,
            "verified": True,
            "plan_steps": [
                "capture_current_state",
                "verify_target_checkpoint",
                "request_execution_approval",
                "execute_via_authorized_runtime_only",
                "verify_post_recovery_state",
            ],
            "execution_allowed_here": False,
        },
        False,
    )


_SENSITIVE_DOCUMENT_MARKERS = (
    "password",
    "api key",
    "secret",
    "social security",
    "ssn",
    "credit card",
    "bank account",
    "private key",
)


def _document_intelligence(payload: Mapping[str, object]) -> AdvancedResult:
    source_id = str(payload.get("source_id") or "").strip()
    raw_sections = payload.get("sections") or []
    max_sections = max(1, min(int(payload.get("max_sections") or 64), 128))

    if not source_id:
        return AdvancedResult(
            "document_intelligence",
            AdvancedBoundary.DATA_REQUIRED,
            "source_id_required",
            {},
            False,
        )
    if not isinstance(raw_sections, list):
        return AdvancedResult(
            "document_intelligence",
            AdvancedBoundary.INVALID_INPUT,
            "sections_must_be_a_list",
            {"source_id": source_id},
            False,
        )

    selected = raw_sections[:max_sections]
    if not selected:
        return AdvancedResult(
            "document_intelligence",
            AdvancedBoundary.DATA_REQUIRED,
            "document_sections_required",
            {"source_id": source_id},
            False,
        )

    seen: set[str] = set()
    pages: set[int] = set()
    sensitive = False
    citation_ids: list[str] = []

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "document_intelligence",
                AdvancedBoundary.INVALID_INPUT,
                "section_must_be_an_object",
                {"source_id": source_id},
                False,
            )

        section_id = str(raw.get("section_id") or "").strip()
        if not section_id or section_id in seen:
            return AdvancedResult(
                "document_intelligence",
                AdvancedBoundary.INVALID_INPUT,
                "section_ids_must_be_unique_and_nonempty",
                {"source_id": source_id},
                False,
            )
        seen.add(section_id)

        if not bool(raw.get("provenance_available", False)):
            return AdvancedResult(
                "document_intelligence",
                AdvancedBoundary.DATA_REQUIRED,
                "section_provenance_required",
                {"source_id": source_id, "section_id": section_id},
                False,
            )

        page = int(raw.get("page") or 0)
        if page <= 0:
            return AdvancedResult(
                "document_intelligence",
                AdvancedBoundary.INVALID_INPUT,
                "positive_page_number_required",
                {"source_id": source_id, "section_id": section_id},
                False,
            )
        pages.add(page)

        text = _norm(raw.get("text"))
        if any(marker in text for marker in _SENSITIVE_DOCUMENT_MARKERS):
            sensitive = True

        citation_ids.append(f"{source_id}:{section_id}")

    return AdvancedResult(
        "document_intelligence",
        AdvancedBoundary.READY,
        "document_metadata_ready",
        {
            "source_id": source_id,
            "section_count": len(selected),
            "page_count": len(pages),
            "citation_ids": citation_ids,
            "citations_supported": True,
            "sensitive_content_detected": sensitive,
            "redaction_required": sensitive,
            "raw_text_returned": False,
            "section_limit_enforced": len(raw_sections) <= max_sections,
        },
        False,
    )


def _data_workspace(payload: Mapping[str, object]) -> AdvancedResult:
    raw_columns = payload.get("columns") or []
    raw_rows = payload.get("rows") or []
    max_rows = max(1, min(int(payload.get("max_rows") or 500), 2000))

    if not isinstance(raw_columns, list) or not raw_columns:
        return AdvancedResult(
            "data_workspace",
            AdvancedBoundary.DATA_REQUIRED,
            "columns_required",
            {},
            False,
        )
    if not isinstance(raw_rows, list):
        return AdvancedResult(
            "data_workspace",
            AdvancedBoundary.INVALID_INPUT,
            "rows_must_be_a_list",
            {},
            False,
        )

    columns: list[str] = []
    seen: set[str] = set()
    for raw in raw_columns[:256]:
        name = str(raw.get("name") if isinstance(raw, dict) else raw).strip()
        if not name or name in seen:
            return AdvancedResult(
                "data_workspace",
                AdvancedBoundary.INVALID_INPUT,
                "column_names_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(name)
        columns.append(name)

    selected_rows = raw_rows[:max_rows]
    missing_counts = {name: 0 for name in columns}
    observed_cells = 0
    for raw in selected_rows:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "data_workspace",
                AdvancedBoundary.INVALID_INPUT,
                "rows_must_be_objects",
                {"row_count": len(selected_rows)},
                False,
            )
        for name in columns:
            observed_cells += 1
            value = raw.get(name)
            if value is None or value == "":
                missing_counts[name] += 1

    row_count = len(selected_rows)
    missing_rates = {
        name: round((missing_counts[name] / row_count), 6) if row_count else 0.0
        for name in columns
    }

    return AdvancedResult(
        "data_workspace",
        AdvancedBoundary.READY,
        "data_profile_ready",
        {
            "column_count": len(columns),
            "row_count_profiled": row_count,
            "missing_rates": missing_rates,
            "sample_limit_enforced": len(raw_rows) <= max_rows,
            "raw_rows_returned": False,
            "dataset_mutated": False,
            "query_executed": False,
            "observed_cells": observed_cells,
        },
        False,
    )


def _safe_repo_path(value: object) -> str | None:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or (len(raw) > 2 and raw[1] == ":"):
        return None
    parts = [part for part in raw.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _code_repository(payload: Mapping[str, object]) -> AdvancedResult:
    raw_files = payload.get("files") or []
    raw_changed = payload.get("changed_paths") or []
    max_files = max(1, min(int(payload.get("max_files") or 300), 1000))
    max_impacted = max(1, min(int(payload.get("max_impacted") or 100), 300))

    if not isinstance(raw_files, list) or not raw_files:
        return AdvancedResult(
            "code_repository",
            AdvancedBoundary.DATA_REQUIRED,
            "repository_files_required",
            {},
            False,
        )
    if not isinstance(raw_changed, list):
        return AdvancedResult(
            "code_repository",
            AdvancedBoundary.INVALID_INPUT,
            "changed_paths_must_be_a_list",
            {},
            False,
        )

    selected = raw_files[:max_files]
    graph: dict[str, tuple[str, ...]] = {}
    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.INVALID_INPUT,
                "file_entries_must_be_objects",
                {},
                False,
            )
        path = _safe_repo_path(raw.get("path"))
        if path is None or path in graph:
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.PROTECTED_TARGET,
                "unsafe_or_duplicate_repository_path",
                {},
                False,
            )

        raw_deps = raw.get("dependencies") or []
        if not isinstance(raw_deps, list):
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.INVALID_INPUT,
                "dependencies_must_be_a_list",
                {"path": path},
                False,
            )
        deps: list[str] = []
        for dep in raw_deps[:128]:
            safe = _safe_repo_path(dep)
            if safe is None:
                return AdvancedResult(
                    "code_repository",
                    AdvancedBoundary.PROTECTED_TARGET,
                    "unsafe_dependency_path",
                    {"path": path},
                    False,
                )
            deps.append(safe)
        graph[path] = tuple(dict.fromkeys(deps))

    changed: list[str] = []
    for raw in raw_changed[:max_impacted]:
        safe = _safe_repo_path(raw)
        if safe is None:
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.PROTECTED_TARGET,
                "unsafe_changed_path",
                {},
                False,
            )
        if safe not in graph:
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.DATA_REQUIRED,
                "changed_path_not_in_repository_snapshot",
                {"changed_path": safe},
                False,
            )
        changed.append(safe)

    reverse: dict[str, set[str]] = {path: set() for path in graph}
    for path, deps in graph.items():
        for dep in deps:
            if dep in reverse:
                reverse[dep].add(path)

    impacted = set(changed)
    frontier = list(changed)
    while frontier and len(impacted) < max_impacted:
        current = frontier.pop(0)
        for dependent in sorted(reverse.get(current, ())):
            if dependent not in impacted:
                impacted.add(dependent)
                frontier.append(dependent)
                if len(impacted) >= max_impacted:
                    break

    return AdvancedResult(
        "code_repository",
        AdvancedBoundary.READY,
        "repository_impact_analysis_ready",
        {
            "file_count_profiled": len(graph),
            "changed_paths": sorted(set(changed)),
            "impacted_paths": sorted(impacted),
            "file_limit_enforced": len(raw_files) <= max_files,
            "impact_limit_enforced": len(impacted) < max_impacted or not frontier,
            "raw_file_content_returned": False,
            "code_execution_performed": False,
            "repository_write_performed": False,
        },
        False,
    )


_RESEARCH_AUTHORITY = {
    "PRIMARY": 4,
    "AUTHORITATIVE": 3,
    "SECONDARY": 2,
    "COMMUNITY": 1,
    "UNKNOWN": 0,
}


def _research_orchestration(payload: Mapping[str, object]) -> AdvancedResult:
    raw_sources = payload.get("sources") or []
    current_required = bool(payload.get("current_required", False))
    max_sources = max(1, min(int(payload.get("max_sources") or 16), 64))
    max_age_days = max(0, min(int(payload.get("max_age_days") or 30), 3650))

    if not isinstance(raw_sources, list) or not raw_sources:
        return AdvancedResult(
            "research_orchestration",
            AdvancedBoundary.DATA_REQUIRED,
            "research_sources_required",
            {"external_fetch_performed": False},
            False,
        )

    ranked: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in raw_sources[:max_sources]:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "research_orchestration",
                AdvancedBoundary.INVALID_INPUT,
                "source_entries_must_be_objects",
                {"external_fetch_performed": False},
                False,
            )

        source_id = str(raw.get("source_id") or "").strip()
        if not source_id or source_id in seen:
            return AdvancedResult(
                "research_orchestration",
                AdvancedBoundary.INVALID_INPUT,
                "source_ids_must_be_unique_and_nonempty",
                {"external_fetch_performed": False},
                False,
            )
        seen.add(source_id)

        if not bool(raw.get("provenance_available", False)):
            return AdvancedResult(
                "research_orchestration",
                AdvancedBoundary.DATA_REQUIRED,
                "source_provenance_required",
                {"source_id": source_id, "external_fetch_performed": False},
                False,
            )

        authority = str(raw.get("authority") or "UNKNOWN").strip().upper()
        if authority not in _RESEARCH_AUTHORITY:
            authority = "UNKNOWN"

        age_days = int(raw.get("age_days") or 0)
        if age_days < 0:
            return AdvancedResult(
                "research_orchestration",
                AdvancedBoundary.INVALID_INPUT,
                "source_age_days_must_be_nonnegative",
                {"source_id": source_id, "external_fetch_performed": False},
                False,
            )

        ranked.append(
            {
                "source_id": source_id,
                "authority": authority,
                "authority_score": _RESEARCH_AUTHORITY[authority],
                "age_days": age_days,
                "fresh": age_days <= max_age_days,
                "claim": _norm(raw.get("claim")),
            }
        )

    ranked.sort(key=lambda item: (-int(item["authority_score"]), int(item["age_days"]), str(item["source_id"])))
    fresh = [item for item in ranked if bool(item["fresh"])]
    authoritative_count = sum(1 for item in ranked if int(item["authority_score"]) >= 3)
    claims = {str(item["claim"]) for item in ranked if str(item["claim"])}

    if current_required and not fresh:
        return AdvancedResult(
            "research_orchestration",
            AdvancedBoundary.DATA_REQUIRED,
            "fresh_current_sources_required",
            {
                "source_count": len(ranked),
                "fresh_source_count": 0,
                "authoritative_source_count": authoritative_count,
                "external_fetch_performed": False,
            },
            False,
        )

    boundary = AdvancedBoundary.CONFLICT if len(claims) > 1 else AdvancedBoundary.READY
    reason = "conflicting_source_claims" if boundary == AdvancedBoundary.CONFLICT else "research_plan_ready"

    return AdvancedResult(
        "research_orchestration",
        boundary,
        reason,
        {
            "selected_source_ids": [str(item["source_id"]) for item in ranked],
            "source_count": len(ranked),
            "fresh_source_count": len(fresh),
            "authoritative_source_count": authoritative_count,
            "current_required": current_required,
            "source_limit_enforced": len(raw_sources) <= max_sources,
            "external_fetch_performed": False,
            "source_content_returned": False,
        },
        False,
    )


def _business_operations(payload: Mapping[str, object]) -> AdvancedResult:
    raw_kpis = payload.get("kpis") or []
    max_kpis = max(1, min(int(payload.get("max_kpis") or 32), 128))

    if not isinstance(raw_kpis, list) or not raw_kpis:
        return AdvancedResult(
            "business_operations",
            AdvancedBoundary.DATA_REQUIRED,
            "business_kpis_required",
            {},
            False,
        )

    selected = raw_kpis[:max_kpis]
    scored: list[dict[str, object]] = []
    seen: set[str] = set()
    weight_total = 0.0
    weighted_score = 0.0

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "business_operations",
                AdvancedBoundary.INVALID_INPUT,
                "kpi_entries_must_be_objects",
                {},
                False,
            )

        name = str(raw.get("name") or "").strip()
        if not name or name in seen:
            return AdvancedResult(
                "business_operations",
                AdvancedBoundary.INVALID_INPUT,
                "kpi_names_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(name)

        value = float(raw.get("value") or 0.0)
        target = float(raw.get("target") or 0.0)
        weight = float(raw.get("weight") or 1.0)
        direction = str(raw.get("direction") or "HIGHER").strip().upper()

        if target <= 0 or weight < 0 or direction not in {"HIGHER", "LOWER"}:
            return AdvancedResult(
                "business_operations",
                AdvancedBoundary.INVALID_INPUT,
                "positive_target_nonnegative_weight_and_valid_direction_required",
                {"kpi": name},
                False,
            )

        if direction == "HIGHER":
            performance = max(0.0, min(1.0, value / target))
        else:
            performance = 1.0 if value <= target else max(0.0, min(1.0, target / value))

        weighted_score += performance * weight
        weight_total += weight
        scored.append(
            {
                "name": name,
                "performance": round(performance, 6),
                "on_target": performance >= 1.0,
                "bottleneck": performance < 0.8,
            }
        )

    if weight_total <= 0:
        return AdvancedResult(
            "business_operations",
            AdvancedBoundary.INVALID_INPUT,
            "positive_total_weight_required",
            {},
            False,
        )

    score = round(weighted_score / weight_total, 6)
    bottlenecks = [
        str(item["name"])
        for item in sorted(scored, key=lambda item: (float(item["performance"]), str(item["name"])))
        if bool(item["bottleneck"])
    ]

    return AdvancedResult(
        "business_operations",
        AdvancedBoundary.READY,
        "business_operations_assessment_ready",
        {
            "operations_score": score,
            "kpi_count": len(scored),
            "bottlenecks": bottlenecks,
            "focus_order": bottlenecks[:5],
            "kpi_limit_enforced": len(raw_kpis) <= max_kpis,
            "pricing_changed": False,
            "staff_dispatched": False,
            "money_spent": False,
            "business_action_executed": False,
        },
        False,
    )


def _financial_planning(payload: Mapping[str, object]) -> AdvancedResult:
    raw_scenarios = payload.get("scenarios") or []
    max_scenarios = max(1, min(int(payload.get("max_scenarios") or 12), 32))

    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        return AdvancedResult(
            "financial_planning",
            AdvancedBoundary.DATA_REQUIRED,
            "financial_scenarios_required",
            {},
            False,
        )

    selected = raw_scenarios[:max_scenarios]
    summaries: list[dict[str, object]] = []
    seen: set[str] = set()
    probability_total = 0.0

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "financial_planning",
                AdvancedBoundary.INVALID_INPUT,
                "scenario_entries_must_be_objects",
                {},
                False,
            )

        name = str(raw.get("name") or "").strip()
        if not name or name in seen:
            return AdvancedResult(
                "financial_planning",
                AdvancedBoundary.INVALID_INPUT,
                "scenario_names_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(name)

        revenue = float(raw.get("revenue") or 0.0)
        costs = float(raw.get("costs") or 0.0)
        investment = float(raw.get("investment") or 0.0)
        probability = float(raw.get("probability") or 1.0)

        if min(revenue, costs, investment, probability) < 0:
            return AdvancedResult(
                "financial_planning",
                AdvancedBoundary.INVALID_INPUT,
                "financial_inputs_must_be_nonnegative",
                {"scenario": name},
                False,
            )

        operating_profit = revenue - costs
        net_after_investment = operating_profit - investment
        roi = (net_after_investment / investment) if investment > 0 else None
        margin = (operating_profit / revenue) if revenue > 0 else None
        break_even_revenue = costs + investment

        probability_total += probability
        summaries.append(
            {
                "name": name,
                "revenue": round(revenue, 2),
                "costs": round(costs, 2),
                "investment": round(investment, 2),
                "probability": probability,
                "operating_profit": round(operating_profit, 2),
                "net_after_investment": round(net_after_investment, 2),
                "roi": round(roi, 6) if roi is not None else None,
                "operating_margin": round(margin, 6) if margin is not None else None,
                "break_even_revenue": round(break_even_revenue, 2),
            }
        )

    if probability_total <= 0:
        return AdvancedResult(
            "financial_planning",
            AdvancedBoundary.INVALID_INPUT,
            "positive_probability_mass_required",
            {},
            False,
        )

    expected_net = sum(
        (float(item["probability"]) / probability_total) * float(item["net_after_investment"])
        for item in summaries
    )

    return AdvancedResult(
        "financial_planning",
        AdvancedBoundary.READY,
        "financial_scenario_analysis_ready",
        {
            "scenario_count": len(summaries),
            "scenarios": summaries,
            "expected_net_after_investment": round(expected_net, 2),
            "scenario_limit_enforced": len(raw_scenarios) <= max_scenarios,
            "decision_support_only": True,
            "transaction_executed": False,
            "personalized_buy_sell_instruction": False,
        },
        False,
    )


def _compliance_policy(payload: Mapping[str, object]) -> AdvancedResult:
    raw_requirements = payload.get("requirements") or []
    raw_evidence = payload.get("evidence_ids") or []
    max_requirements = max(1, min(int(payload.get("max_requirements") or 64), 256))

    if not isinstance(raw_requirements, list) or not raw_requirements:
        return AdvancedResult(
            "compliance_policy",
            AdvancedBoundary.DATA_REQUIRED,
            "compliance_requirements_required",
            {},
            False,
        )

    if not isinstance(raw_evidence, list):
        return AdvancedResult(
            "compliance_policy",
            AdvancedBoundary.INVALID_INPUT,
            "evidence_ids_must_be_a_list",
            {},
            False,
        )

    evidence = {str(item).strip() for item in raw_evidence if str(item).strip()}
    selected = raw_requirements[:max_requirements]
    seen: set[str] = set()
    rows: list[dict[str, object]] = []
    mandatory_missing: list[str] = []

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "compliance_policy",
                AdvancedBoundary.INVALID_INPUT,
                "requirement_entries_must_be_objects",
                {},
                False,
            )

        requirement_id = str(raw.get("requirement_id") or "").strip()
        if not requirement_id or requirement_id in seen:
            return AdvancedResult(
                "compliance_policy",
                AdvancedBoundary.INVALID_INPUT,
                "requirement_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(requirement_id)

        mandatory = bool(raw.get("mandatory", True))
        required_evidence = {
            str(item).strip()
            for item in (raw.get("required_evidence_ids") or [])
            if str(item).strip()
        }
        missing = sorted(required_evidence - evidence)
        satisfied = not missing

        if mandatory and not satisfied:
            mandatory_missing.append(requirement_id)

        rows.append(
            {
                "requirement_id": requirement_id,
                "mandatory": mandatory,
                "satisfied": satisfied,
                "missing_evidence_ids": missing,
            }
        )

    boundary = AdvancedBoundary.DATA_REQUIRED if mandatory_missing else AdvancedBoundary.READY
    reason = "mandatory_evidence_missing" if mandatory_missing else "compliance_evidence_review_ready"

    return AdvancedResult(
        "compliance_policy",
        boundary,
        reason,
        {
            "requirement_count": len(rows),
            "mandatory_missing": mandatory_missing,
            "requirements": rows,
            "requirement_limit_enforced": len(raw_requirements) <= max_requirements,
            "certification_issued": False,
            "legal_conclusion_issued": False,
            "policy_changed": False,
            "permission_changed": False,
            "decision_support_only": True,
        },
        False,
    )


def _incident_triage(payload: Mapping[str, object]) -> AdvancedResult:
    raw_incidents = payload.get("incidents") or []
    max_incidents = max(1, min(int(payload.get("max_incidents") or 64), 256))

    if not isinstance(raw_incidents, list) or not raw_incidents:
        return AdvancedResult(
            "incident_triage",
            AdvancedBoundary.DATA_REQUIRED,
            "incidents_required",
            {},
            False,
        )

    severity_weight = {
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4,
    }
    selected = raw_incidents[:max_incidents]
    seen: set[str] = set()
    rows: list[dict[str, object]] = []

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "incident_triage",
                AdvancedBoundary.INVALID_INPUT,
                "incident_entries_must_be_objects",
                {},
                False,
            )

        incident_id = str(raw.get("incident_id") or "").strip()
        severity = str(raw.get("severity") or "").strip().upper()
        confidence = max(0.0, min(1.0, float(raw.get("confidence") or 0.0)))
        affected = max(0, int(raw.get("affected_units") or 0))

        if not incident_id or incident_id in seen:
            return AdvancedResult(
                "incident_triage",
                AdvancedBoundary.INVALID_INPUT,
                "incident_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        if severity not in severity_weight:
            return AdvancedResult(
                "incident_triage",
                AdvancedBoundary.INVALID_INPUT,
                "severity_must_be_low_medium_high_or_critical",
                {"incident_id": incident_id},
                False,
            )

        seen.add(incident_id)
        score = severity_weight[severity] * 1000 + affected * 2 + int(confidence * 100)
        rows.append(
            {
                "incident_id": incident_id,
                "severity": severity,
                "confidence": round(confidence, 6),
                "affected_units": affected,
                "priority_score": score,
                "escalation_required": severity in {"HIGH", "CRITICAL"},
            }
        )

    ranked = sorted(rows, key=lambda row: (-int(row["priority_score"]), str(row["incident_id"])))
    return AdvancedResult(
        "incident_triage",
        AdvancedBoundary.READY,
        "incident_triage_ready",
        {
            "incident_count": len(ranked),
            "priority_order": [str(row["incident_id"]) for row in ranked],
            "incidents": ranked,
            "incident_limit_enforced": len(raw_incidents) <= max_incidents,
            "remediation_executed": False,
            "service_restarted": False,
            "notification_sent": False,
            "human_escalation_dispatched": False,
        },
        False,
    )


def _resource_capacity(payload: Mapping[str, object]) -> AdvancedResult:
    raw_resources = payload.get("resources") or []
    max_resources = max(1, min(int(payload.get("max_resources") or 64), 256))

    if not isinstance(raw_resources, list) or not raw_resources:
        return AdvancedResult(
            "resource_capacity",
            AdvancedBoundary.DATA_REQUIRED,
            "resources_required",
            {},
            False,
        )

    selected = raw_resources[:max_resources]
    seen: set[str] = set()
    rows: list[dict[str, object]] = []
    shortages: list[str] = []

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "resource_capacity",
                AdvancedBoundary.INVALID_INPUT,
                "resource_entries_must_be_objects",
                {},
                False,
            )

        resource_id = str(raw.get("resource_id") or "").strip()
        capacity = float(raw.get("capacity") or 0.0)
        demand = float(raw.get("demand") or 0.0)
        reserve = float(raw.get("reserve") or 0.0)

        if not resource_id or resource_id in seen:
            return AdvancedResult(
                "resource_capacity",
                AdvancedBoundary.INVALID_INPUT,
                "resource_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        if capacity < 0 or demand < 0 or reserve < 0 or reserve > capacity:
            return AdvancedResult(
                "resource_capacity",
                AdvancedBoundary.INVALID_INPUT,
                "capacity_demand_and_reserve_must_be_valid_nonnegative_values",
                {"resource_id": resource_id},
                False,
            )

        seen.add(resource_id)
        usable_capacity = max(0.0, capacity - reserve)
        shortage = max(0.0, demand - usable_capacity)
        utilization = (demand / usable_capacity) if usable_capacity > 0 else (1.0 if demand > 0 else 0.0)
        if shortage > 0:
            shortages.append(resource_id)

        rows.append(
            {
                "resource_id": resource_id,
                "capacity": round(capacity, 6),
                "reserve": round(reserve, 6),
                "usable_capacity": round(usable_capacity, 6),
                "demand": round(demand, 6),
                "utilization": round(utilization, 6),
                "shortage": round(shortage, 6),
                "over_capacity": shortage > 0,
            }
        )

    rows.sort(key=lambda row: (-float(row["utilization"]), str(row["resource_id"])))
    return AdvancedResult(
        "resource_capacity",
        AdvancedBoundary.READY,
        "resource_capacity_analysis_ready",
        {
            "resource_count": len(rows),
            "resources": rows,
            "shortage_resource_ids": shortages,
            "resource_limit_enforced": len(raw_resources) <= max_resources,
            "provisioning_performed": False,
            "hiring_performed": False,
            "purchase_performed": False,
            "allocation_changed": False,
        },
        False,
    )


def _change_impact(payload: Mapping[str, object]) -> AdvancedResult:
    raw_components = payload.get("components") or []
    raw_changed = payload.get("changed_component_ids") or []
    max_components = max(1, min(int(payload.get("max_components") or 256), 1000))

    if not isinstance(raw_components, list) or not raw_components:
        return AdvancedResult(
            "change_impact",
            AdvancedBoundary.DATA_REQUIRED,
            "components_required",
            {},
            False,
        )
    if not isinstance(raw_changed, list) or not raw_changed:
        return AdvancedResult(
            "change_impact",
            AdvancedBoundary.DATA_REQUIRED,
            "changed_component_ids_required",
            {},
            False,
        )

    selected = raw_components[:max_components]
    components: dict[str, dict[str, object]] = {}
    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "change_impact",
                AdvancedBoundary.INVALID_INPUT,
                "component_entries_must_be_objects",
                {},
                False,
            )
        component_id = str(raw.get("component_id") or "").strip()
        if not component_id or component_id in components:
            return AdvancedResult(
                "change_impact",
                AdvancedBoundary.INVALID_INPUT,
                "component_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        criticality = int(raw.get("criticality") or 1)
        if criticality < 1 or criticality > 5:
            return AdvancedResult(
                "change_impact",
                AdvancedBoundary.INVALID_INPUT,
                "criticality_must_be_between_1_and_5",
                {"component_id": component_id},
                False,
            )
        dependencies = tuple(str(item).strip() for item in (raw.get("dependencies") or []) if str(item).strip())
        components[component_id] = {
            "dependencies": dependencies,
            "criticality": criticality,
        }

    for component_id, row in components.items():
        unknown = [dep for dep in row["dependencies"] if dep not in components]
        if unknown:
            return AdvancedResult(
                "change_impact",
                AdvancedBoundary.INVALID_INPUT,
                "unknown_component_dependency",
                {"component_id": component_id, "unknown_dependencies": unknown},
                False,
            )

    changed = {str(item).strip() for item in raw_changed if str(item).strip()}
    unknown_changed = sorted(changed - set(components))
    if unknown_changed:
        return AdvancedResult(
            "change_impact",
            AdvancedBoundary.INVALID_INPUT,
            "unknown_changed_components",
            {"unknown_changed_components": unknown_changed},
            False,
        )

    reverse: dict[str, set[str]] = {component_id: set() for component_id in components}
    for component_id, row in components.items():
        for dep in row["dependencies"]:
            reverse[dep].add(component_id)

    impacted = set(changed)
    frontier = set(changed)
    while frontier:
        next_frontier: set[str] = set()
        for component_id in frontier:
            for dependent in reverse[component_id]:
                if dependent not in impacted:
                    impacted.add(dependent)
                    next_frontier.add(dependent)
        frontier = next_frontier

    ranked = sorted(
        impacted,
        key=lambda component_id: (-int(components[component_id]["criticality"]), component_id),
    )
    max_criticality = max(int(components[item]["criticality"]) for item in impacted)
    risk = "HIGH" if max_criticality >= 5 or len(impacted) > max(3, len(components) // 2) else ("MEDIUM" if max_criticality >= 3 else "LOW")

    return AdvancedResult(
        "change_impact",
        AdvancedBoundary.READY,
        "change_impact_analysis_ready",
        {
            "changed_component_ids": sorted(changed),
            "impacted_component_ids": ranked,
            "blast_radius_count": len(impacted),
            "total_component_count": len(components),
            "max_criticality": max_criticality,
            "risk_level": risk,
            "component_limit_enforced": len(raw_components) <= max_components,
            "code_changed": False,
            "configuration_changed": False,
            "migration_executed": False,
            "deployment_executed": False,
        },
        False,
    )


def _experiment_causal(payload: Mapping[str, object]) -> AdvancedResult:
    control = payload.get("control") or {}
    treatment = payload.get("treatment") or {}

    if not isinstance(control, dict) or not isinstance(treatment, dict):
        return AdvancedResult(
            "experiment_causal",
            AdvancedBoundary.INVALID_INPUT,
            "control_and_treatment_must_be_objects",
            {},
            False,
        )

    required = ("mean", "sample_size")
    if any(key not in control for key in required) or any(key not in treatment for key in required):
        return AdvancedResult(
            "experiment_causal",
            AdvancedBoundary.DATA_REQUIRED,
            "group_mean_and_sample_size_required",
            {},
            False,
        )

    control_mean = float(control.get("mean") or 0.0)
    treatment_mean = float(treatment.get("mean") or 0.0)
    control_n = int(control.get("sample_size") or 0)
    treatment_n = int(treatment.get("sample_size") or 0)

    if control_n <= 0 or treatment_n <= 0:
        return AdvancedResult(
            "experiment_causal",
            AdvancedBoundary.INVALID_INPUT,
            "positive_sample_sizes_required",
            {},
            False,
        )

    absolute_effect = treatment_mean - control_mean
    relative_lift = (absolute_effect / control_mean) if control_mean != 0 else None
    randomized = bool(payload.get("randomized", False))
    verified_design = bool(payload.get("verified_design", False))
    confounders = [
        str(item).strip()
        for item in (payload.get("known_confounders") or [])[:32]
        if str(item).strip()
    ]

    causal_support = randomized and verified_design and not confounders
    interpretation = (
        "CAUSAL_EVIDENCE_SUPPORTED"
        if causal_support
        else "ASSOCIATION_ONLY"
    )

    return AdvancedResult(
        "experiment_causal",
        AdvancedBoundary.READY,
        "experiment_analysis_ready",
        {
            "control_mean": round(control_mean, 6),
            "treatment_mean": round(treatment_mean, 6),
            "control_sample_size": control_n,
            "treatment_sample_size": treatment_n,
            "absolute_effect": round(absolute_effect, 6),
            "relative_lift": round(relative_lift, 6) if relative_lift is not None else None,
            "randomized": randomized,
            "verified_design": verified_design,
            "known_confounders": confounders,
            "causal_interpretation": interpretation,
            "causal_claim_supported": causal_support,
            "experiment_launched": False,
            "traffic_randomized": False,
            "participants_enrolled": False,
        },
        False,
    )


def _forecast_trend(payload: Mapping[str, object]) -> AdvancedResult:
    raw_values = payload.get("values") or []
    horizon = int(payload.get("horizon") or 1)
    max_points = max(2, min(int(payload.get("max_points") or 500), 5000))
    max_horizon = max(1, min(int(payload.get("max_horizon") or 12), 52))

    if not isinstance(raw_values, list) or len(raw_values) < 2:
        return AdvancedResult(
            "forecast_trend",
            AdvancedBoundary.DATA_REQUIRED,
            "at_least_two_values_required",
            {},
            False,
        )
    if horizon <= 0 or horizon > max_horizon:
        return AdvancedResult(
            "forecast_trend",
            AdvancedBoundary.INVALID_INPUT,
            "horizon_out_of_bounds",
            {"max_horizon": max_horizon},
            False,
        )

    selected = [float(item) for item in raw_values[-max_points:]]
    n = len(selected)
    x_mean = (n - 1) / 2.0
    y_mean = sum(selected) / n
    denominator = sum((index - x_mean) ** 2 for index in range(n))
    slope = (
        sum((index - x_mean) * (value - y_mean) for index, value in enumerate(selected)) / denominator
        if denominator > 0
        else 0.0
    )
    intercept = y_mean - slope * x_mean
    fitted = [intercept + slope * index for index in range(n)]
    mae = sum(abs(actual - estimate) for actual, estimate in zip(selected, fitted)) / n
    projected = [
        intercept + slope * (n + step)
        for step in range(horizon)
    ]

    if abs(slope) < 1e-12:
        direction = "FLAT"
    elif slope > 0:
        direction = "UP"
    else:
        direction = "DOWN"

    return AdvancedResult(
        "forecast_trend",
        AdvancedBoundary.READY,
        "bounded_trend_projection_ready",
        {
            "point_count": n,
            "trend_direction": direction,
            "slope_per_period": round(slope, 6),
            "mean_absolute_fit_error": round(mae, 6),
            "horizon": horizon,
            "projected_values": [round(value, 6) for value in projected],
            "point_limit_enforced": len(raw_values) <= max_points,
            "external_data_fetched": False,
            "forecast_guaranteed": False,
            "trade_executed": False,
            "financial_transaction_executed": False,
        },
        False,
    )


def _approval_governance(payload: Mapping[str, object]) -> AdvancedResult:
    raw_approvals = payload.get("approvals") or []
    required_approvals = int(payload.get("required_approvals") or 1)
    allowed_roles = {
        str(item).strip().lower()
        for item in (payload.get("allowed_roles") or [])
        if str(item).strip()
    }
    max_approvals = max(1, min(int(payload.get("max_approvals") or 32), 128))

    if required_approvals <= 0:
        return AdvancedResult(
            "approval_governance",
            AdvancedBoundary.INVALID_INPUT,
            "required_approvals_must_be_positive",
            {},
            False,
        )
    if not isinstance(raw_approvals, list):
        return AdvancedResult(
            "approval_governance",
            AdvancedBoundary.INVALID_INPUT,
            "approvals_must_be_a_list",
            {},
            False,
        )

    selected = raw_approvals[:max_approvals]
    seen: set[str] = set()
    verified_approvers: list[str] = []
    rejected_entries: list[str] = []

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "approval_governance",
                AdvancedBoundary.INVALID_INPUT,
                "approval_entries_must_be_objects",
                {},
                False,
            )

        actor_id = str(raw.get("actor_id") or "").strip()
        role = str(raw.get("role") or "").strip().lower()
        approved = bool(raw.get("approved", False))
        verified = bool(raw.get("verified", False))

        if not actor_id or actor_id in seen:
            return AdvancedResult(
                "approval_governance",
                AdvancedBoundary.INVALID_INPUT,
                "approval_actor_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(actor_id)

        if allowed_roles and role not in allowed_roles:
            rejected_entries.append(actor_id)
            continue

        if approved and verified:
            verified_approvers.append(actor_id)

    quorum_met = len(verified_approvers) >= required_approvals
    boundary = AdvancedBoundary.READY if quorum_met else AdvancedBoundary.DATA_REQUIRED
    reason = "verified_human_approval_quorum_met" if quorum_met else "verified_human_approval_quorum_required"

    return AdvancedResult(
        "approval_governance",
        boundary,
        reason,
        {
            "required_approvals": required_approvals,
            "verified_approval_count": len(verified_approvers),
            "verified_approver_ids": sorted(verified_approvers),
            "rejected_actor_ids": sorted(rejected_entries),
            "quorum_met": quorum_met,
            "approval_limit_enforced": len(raw_approvals) <= max_approvals,
            "self_approval_used": False,
            "approval_token_issued": False,
            "permission_changed": False,
            "action_executed": False,
        },
        False,
    )


def _resilience_fallback(payload: Mapping[str, object]) -> AdvancedResult:
    raw_candidates = payload.get("candidates") or []
    max_candidates = max(1, min(int(payload.get("max_candidates") or 32), 128))

    if not isinstance(raw_candidates, list) or not raw_candidates:
        return AdvancedResult(
            "resilience_fallback",
            AdvancedBoundary.DATA_REQUIRED,
            "fallback_candidates_required",
            {},
            False,
        )

    selected = raw_candidates[:max_candidates]
    seen: set[str] = set()
    rows: list[dict[str, object]] = []

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "resilience_fallback",
                AdvancedBoundary.INVALID_INPUT,
                "fallback_entries_must_be_objects",
                {},
                False,
            )

        candidate_id = str(raw.get("candidate_id") or "").strip()
        priority = int(raw.get("priority") or 100)
        healthy = bool(raw.get("healthy", False))
        eligible = bool(raw.get("fallback_eligible", True))

        if not candidate_id or candidate_id in seen:
            return AdvancedResult(
                "resilience_fallback",
                AdvancedBoundary.INVALID_INPUT,
                "candidate_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        if priority < 0:
            return AdvancedResult(
                "resilience_fallback",
                AdvancedBoundary.INVALID_INPUT,
                "priority_must_be_nonnegative",
                {"candidate_id": candidate_id},
                False,
            )

        seen.add(candidate_id)
        rows.append(
            {
                "candidate_id": candidate_id,
                "priority": priority,
                "healthy": healthy,
                "fallback_eligible": eligible,
            }
        )

    ordered = sorted(rows, key=lambda row: (int(row["priority"]), str(row["candidate_id"])))
    healthy_eligible = [
        row for row in ordered
        if bool(row["healthy"]) and bool(row["fallback_eligible"])
    ]

    if not healthy_eligible:
        return AdvancedResult(
            "resilience_fallback",
            AdvancedBoundary.DATA_REQUIRED,
            "no_healthy_eligible_fallback",
            {
                "candidate_count": len(rows),
                "candidate_limit_enforced": len(raw_candidates) <= max_candidates,
                "failover_executed": False,
                "traffic_switched": False,
                "service_restarted": False,
                "configuration_changed": False,
            },
            False,
        )

    primary = healthy_eligible[0]
    fallback_chain = [str(row["candidate_id"]) for row in healthy_eligible[1:]]
    degraded = any(not bool(row["healthy"]) for row in ordered)

    return AdvancedResult(
        "resilience_fallback",
        AdvancedBoundary.READY,
        "fallback_plan_ready",
        {
            "selected_primary": str(primary["candidate_id"]),
            "fallback_chain": fallback_chain,
            "degraded_input_state": degraded,
            "candidate_count": len(rows),
            "candidate_limit_enforced": len(raw_candidates) <= max_candidates,
            "failover_executed": False,
            "traffic_switched": False,
            "service_restarted": False,
            "configuration_changed": False,
        },
        False,
    )


def _release_readiness(payload: Mapping[str, object]) -> AdvancedResult:
    raw_checks = payload.get("checks") or []
    max_checks = max(1, min(int(payload.get("max_checks") or 128), 512))

    if not isinstance(raw_checks, list) or not raw_checks:
        return AdvancedResult(
            "release_readiness",
            AdvancedBoundary.DATA_REQUIRED,
            "release_checks_required",
            {},
            False,
        )

    selected = raw_checks[:max_checks]
    seen: set[str] = set()
    rows: list[dict[str, object]] = []
    blockers: list[str] = []
    missing_verified_evidence: list[str] = []

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "release_readiness",
                AdvancedBoundary.INVALID_INPUT,
                "release_check_entries_must_be_objects",
                {},
                False,
            )

        check_id = str(raw.get("check_id") or "").strip()
        category = str(raw.get("category") or "general").strip().lower()
        required = bool(raw.get("required", True))
        passed = bool(raw.get("passed", False))
        verified = bool(raw.get("verified", False))

        if not check_id or check_id in seen:
            return AdvancedResult(
                "release_readiness",
                AdvancedBoundary.INVALID_INPUT,
                "check_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(check_id)

        if required and not passed:
            blockers.append(check_id)
        if required and passed and not verified:
            missing_verified_evidence.append(check_id)

        rows.append(
            {
                "check_id": check_id,
                "category": category,
                "required": required,
                "passed": passed,
                "verified": verified,
            }
        )

    if blockers:
        boundary = AdvancedBoundary.CONFLICT
        reason = "required_release_checks_failed"
    elif missing_verified_evidence:
        boundary = AdvancedBoundary.DATA_REQUIRED
        reason = "verified_release_evidence_required"
    else:
        boundary = AdvancedBoundary.READY
        reason = "release_readiness_review_ready"

    return AdvancedResult(
        "release_readiness",
        boundary,
        reason,
        {
            "check_count": len(rows),
            "blocker_check_ids": sorted(blockers),
            "unverified_required_check_ids": sorted(missing_verified_evidence),
            "checks": rows,
            "check_limit_enforced": len(raw_checks) <= max_checks,
            "release_ready": not blockers and not missing_verified_evidence,
            "deployment_executed": False,
            "publication_executed": False,
            "merge_executed": False,
            "promotion_executed": False,
        },
        False,
    )


def _integrated_platform(payload: Mapping[str, object]) -> AdvancedResult:
    raw_subsystems = payload.get("subsystems") or []
    max_subsystems = max(1, min(int(payload.get("max_subsystems") or 128), 512))

    if not isinstance(raw_subsystems, list) or not raw_subsystems:
        return AdvancedResult(
            "integrated_platform",
            AdvancedBoundary.DATA_REQUIRED,
            "subsystem_statuses_required",
            {},
            False,
        )

    selected = raw_subsystems[:max_subsystems]
    seen: set[str] = set()
    unavailable: list[str] = []
    unverified: list[str] = []
    unbounded: list[str] = []
    rows: list[dict[str, object]] = []

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "integrated_platform",
                AdvancedBoundary.INVALID_INPUT,
                "subsystem_entries_must_be_objects",
                {},
                False,
            )

        capability_id = str(raw.get("capability_id") or "").strip()
        available = bool(raw.get("available", False))
        verified = bool(raw.get("verified", False))
        bounded = bool(raw.get("bounded", False))
        required = bool(raw.get("required", True))

        if not capability_id or capability_id in seen:
            return AdvancedResult(
                "integrated_platform",
                AdvancedBoundary.INVALID_INPUT,
                "capability_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(capability_id)

        if required and not available:
            unavailable.append(capability_id)
        if required and available and not verified:
            unverified.append(capability_id)
        if required and available and verified and not bounded:
            unbounded.append(capability_id)

        rows.append(
            {
                "capability_id": capability_id,
                "required": required,
                "available": available,
                "verified": verified,
                "bounded": bounded,
            }
        )

    if unavailable or unverified:
        boundary = AdvancedBoundary.DATA_REQUIRED
        reason = "required_subsystem_evidence_incomplete"
    elif unbounded:
        boundary = AdvancedBoundary.CONFLICT
        reason = "required_subsystem_not_safely_bounded"
    else:
        boundary = AdvancedBoundary.READY
        reason = "integrated_platform_review_ready"

    return AdvancedResult(
        "integrated_platform",
        boundary,
        reason,
        {
            "subsystem_count": len(rows),
            "unavailable_capability_ids": sorted(unavailable),
            "unverified_capability_ids": sorted(unverified),
            "unbounded_capability_ids": sorted(unbounded),
            "subsystems": rows,
            "subsystem_limit_enforced": len(raw_subsystems) <= max_subsystems,
            "integrated_ready": not unavailable and not unverified and not unbounded,
            "production_deployed": False,
            "permission_expanded": False,
            "security_policy_rewritten": False,
            "autonomous_side_effects_enabled": False,
        },
        False,
    )


_EVALUATORS = {
    "recovery_rollback": _recovery_rollback,
    "document_intelligence": _document_intelligence,
    "data_workspace": _data_workspace,
    "code_repository": _code_repository,
    "research_orchestration": _research_orchestration,
    "business_operations": _business_operations,
    "financial_planning": _financial_planning,
    "compliance_policy": _compliance_policy,
    "incident_triage": _incident_triage,
    "resource_capacity": _resource_capacity,
    "change_impact": _change_impact,
    "experiment_causal": _experiment_causal,
    "forecast_trend": _forecast_trend,
    "approval_governance": _approval_governance,
    "resilience_fallback": _resilience_fallback,
    "release_readiness": _release_readiness,
    "integrated_platform": _integrated_platform,
}


def available_advanced_capabilities() -> tuple[str, ...]:
    return tuple(sorted(_EVALUATORS))


def evaluate_advanced_capability(
    capability: str,
    payload: Mapping[str, object],
) -> AdvancedResult:
    key = _norm(capability).replace(" ", "_")
    evaluator = _EVALUATORS.get(key)
    if evaluator is None:
        return AdvancedResult(
            key,
            AdvancedBoundary.INVALID_INPUT,
            "unsupported_advanced_capability",
            {"available_capabilities": list(available_advanced_capabilities())},
            False,
        )
    return evaluator(payload)


def public_advanced_result(result: AdvancedResult) -> dict[str, object]:
    return {
        "capability": result.capability,
        "boundary": result.boundary.value,
        "reason": result.reason,
        "payload": dict(result.payload),
        "side_effect_performed": result.side_effect_performed,
    }
