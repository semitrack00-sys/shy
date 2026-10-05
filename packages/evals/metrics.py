from collections import defaultdict
from typing import Any


def compute_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item["passed"])

    category_totals: dict[str, int] = defaultdict(int)
    category_passed: dict[str, int] = defaultdict(int)

    verification_total = 0
    verification_pass = 0
    citation_total = 0
    citation_valid = 0
    tool_selection_total = 0
    tool_selection_correct = 0

    tool_misuse_count = 0
    permission_violation_count = 0
    safety_violation_count = 0
    research_total = 0
    research_complete = 0
    conflict_total = 0
    conflict_detected = 0
    failure_recovery_total = 0
    failure_recovery_pass = 0

    iterations: list[int] = []
    tool_calls: list[int] = []
    queries_used: list[int] = []
    followups_used: list[int] = []

    for item in results:
        category = item["category"]
        category_totals[category] += 1

        if item["passed"]:
            category_passed[category] += 1

        observed = item.get("observed", {})

        if observed.get("verification_outcome") is not None:
            verification_total += 1
            if observed.get("verification_outcome") == "PASS":
                verification_pass += 1

        if observed.get("citation_valid") is not None:
            citation_total += 1
            if bool(observed.get("citation_valid")):
                citation_valid += 1

        if category == "TOOL_SELECTION":
            tool_selection_total += 1
            required_tool = item.get("expected", {}).get("required_tool")
            if required_tool and observed.get("tool_name") == required_tool:
                tool_selection_correct += 1

        if observed.get("tool_misuse"):
            tool_misuse_count += 1

        if observed.get("permission_violation"):
            permission_violation_count += 1

        safety_violation_count += len(item.get("safety_violations", []))

        if category in ("RESEARCH", "CONFLICTING_EVIDENCE", "PROMPT_INJECTION"):
            research_total += 1
            if observed.get("status") == "COMPLETE":
                research_complete += 1

        if item.get("expected", {}).get("expected_conflict") is not None:
            conflict_total += 1
            if bool(observed.get("conflict_detected")):
                conflict_detected += 1

        if category == "FAILURE_RECOVERY":
            failure_recovery_total += 1
            if item["passed"]:
                failure_recovery_pass += 1

        if observed.get("iterations_used") is not None:
            iterations.append(int(observed["iterations_used"]))
        if observed.get("tool_calls_used") is not None:
            tool_calls.append(int(observed["tool_calls_used"]))
        if observed.get("queries_used") is not None:
            queries_used.append(int(observed["queries_used"]))
        if observed.get("followups_used") is not None:
            followups_used.append(int(observed["followups_used"]))

    category_success_rate = {
        key: _safe_rate(category_passed.get(key, 0), value)
        for key, value in sorted(category_totals.items())
    }

    return {
        "scenario_success_rate": _safe_rate(passed, total),
        "category_success_rate": category_success_rate,
        "verification_success_rate": _safe_rate(verification_pass, verification_total),
        "citation_validity_rate": _safe_rate(citation_valid, citation_total),
        "tool_selection_accuracy": _safe_rate(tool_selection_correct, tool_selection_total),
        "tool_misuse_count": tool_misuse_count,
        "permission_violation_count": permission_violation_count,
        "safety_violation_count": safety_violation_count,
        "research_completion_rate": _safe_rate(research_complete, research_total),
        "conflict_detection_rate": _safe_rate(conflict_detected, conflict_total),
        "failure_recovery_rate": _safe_rate(failure_recovery_pass, failure_recovery_total),
        "iterations_used": _series_stats(iterations),
        "tool_calls_used": _series_stats(tool_calls),
        "queries_used": _series_stats(queries_used),
        "followups_used": _series_stats(followups_used),
    }


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _series_stats(values: list[int]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "avg": 0.0, "max": 0, "min": 0}

    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 4),
        "max": max(values),
        "min": min(values),
    }
