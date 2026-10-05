import argparse
import json
from pathlib import Path
from typing import Any

from .regression import evaluate_regression_policy


def compare_reports(
    baseline_report: dict[str, Any],
    candidate_report: dict[str, Any],
    quality_regression_tolerance: float = 0.0,
) -> dict[str, Any]:
    baseline_by_id = {
        item["scenario_id"]: item
        for item in baseline_report.get("results", [])
    }
    candidate_by_id = {
        item["scenario_id"]: item
        for item in candidate_report.get("results", [])
    }

    all_ids = sorted(set(baseline_by_id) | set(candidate_by_id))

    new_passes: list[str] = []
    new_failures: list[str] = []
    unchanged_passes: list[str] = []
    unchanged_failures: list[str] = []

    for scenario_id in all_ids:
        baseline = baseline_by_id.get(scenario_id)
        candidate = candidate_by_id.get(scenario_id)

        base_pass = bool(baseline and baseline.get("passed"))
        cand_pass = bool(candidate and candidate.get("passed"))

        if not base_pass and cand_pass:
            new_passes.append(scenario_id)
        elif base_pass and not cand_pass:
            new_failures.append(scenario_id)
        elif base_pass and cand_pass:
            unchanged_passes.append(scenario_id)
        else:
            unchanged_failures.append(scenario_id)

    category_deltas = _category_deltas(baseline_report, candidate_report)
    metric_deltas = _metric_deltas(baseline_report, candidate_report)

    baseline_safety = _safety_set(baseline_report)
    candidate_safety = _safety_set(candidate_report)

    new_safety_violations = sorted(candidate_safety - baseline_safety)
    resolved_safety_violations = sorted(baseline_safety - candidate_safety)

    regression = evaluate_regression_policy(
        baseline_report,
        candidate_report,
        quality_regression_tolerance=quality_regression_tolerance,
    )

    return {
        "new_passes": new_passes,
        "new_failures": new_failures,
        "unchanged_passes": unchanged_passes,
        "unchanged_failures": unchanged_failures,
        "category_deltas": category_deltas,
        "metric_deltas": metric_deltas,
        "new_safety_violations": new_safety_violations,
        "resolved_safety_violations": resolved_safety_violations,
        "regression_policy": regression,
    }


def _category_deltas(baseline_report: dict[str, Any], candidate_report: dict[str, Any]) -> dict[str, float]:
    baseline = baseline_report.get("category_results", {})
    candidate = candidate_report.get("category_results", {})

    categories = sorted(set(baseline) | set(candidate))
    deltas: dict[str, float] = {}

    for category in categories:
        before = float(baseline.get(category, {}).get("pass_rate", 0.0))
        after = float(candidate.get(category, {}).get("pass_rate", 0.0))
        deltas[category] = round(after - before, 4)

    return deltas


def _metric_deltas(baseline_report: dict[str, Any], candidate_report: dict[str, Any]) -> dict[str, float]:
    baseline = baseline_report.get("metrics", {})
    candidate = candidate_report.get("metrics", {})

    scalar_keys = (
        "scenario_success_rate",
        "verification_success_rate",
        "citation_validity_rate",
        "tool_selection_accuracy",
        "tool_misuse_count",
        "permission_violation_count",
        "safety_violation_count",
        "research_completion_rate",
        "conflict_detection_rate",
        "failure_recovery_rate",
    )

    deltas: dict[str, float] = {}

    for key in scalar_keys:
        before = float(baseline.get(key, 0.0))
        after = float(candidate.get(key, 0.0))
        deltas[key] = round(after - before, 4)

    return deltas


def _safety_set(report: dict[str, Any]) -> set[str]:
    values: set[str] = set()

    for row in report.get("safety_violations", []):
        scenario_id = str(row.get("scenario_id", ""))
        code = str(row.get("code", ""))
        values.add(f"{scenario_id}:{code}")

    return values


def _load_report(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare SHY evaluation reports.")
    parser.add_argument("baseline", help="Path to baseline report JSON")
    parser.add_argument("candidate", help="Path to candidate report JSON")
    parser.add_argument("--quality-tolerance", type=float, default=0.0)

    args = parser.parse_args(argv)

    baseline_report = _load_report(args.baseline)
    candidate_report = _load_report(args.candidate)

    comparison = compare_reports(
        baseline_report,
        candidate_report,
        quality_regression_tolerance=args.quality_tolerance,
    )

    print("Scenario changes:")
    print(f"  New passes: {len(comparison['new_passes'])}")
    print(f"  New failures: {len(comparison['new_failures'])}")
    print(f"  Unchanged passes: {len(comparison['unchanged_passes'])}")
    print(f"  Unchanged failures: {len(comparison['unchanged_failures'])}")

    print("Category deltas:")
    for category, delta in comparison["category_deltas"].items():
        print(f"  {category}: {delta}")

    print("Metric deltas:")
    for metric, delta in comparison["metric_deltas"].items():
        print(f"  {metric}: {delta}")

    print(f"New safety violations: {len(comparison['new_safety_violations'])}")
    print(f"Resolved safety violations: {len(comparison['resolved_safety_violations'])}")
    print(f"Regression policy passed: {comparison['regression_policy']['passed']}")

    return 0 if comparison["regression_policy"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
