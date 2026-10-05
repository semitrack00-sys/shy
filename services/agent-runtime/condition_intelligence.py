from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


class ConditionOperator(str, Enum):
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    EQ = "EQ"
    NEQ = "NEQ"


class ConditionBoundary(str, Enum):
    EVALUATED = "EVALUATED"
    MISSING_METRIC = "MISSING_METRIC"
    INVALID_RULE = "INVALID_RULE"


@dataclass(frozen=True)
class ConditionRule:
    rule_id: str
    metric: str
    operator: ConditionOperator
    threshold: float


@dataclass(frozen=True)
class ConditionResult:
    rule_id: str
    metric: str
    boundary: ConditionBoundary
    matched: bool
    observed_value: float | None
    threshold: float
    reason: str


@dataclass(frozen=True)
class ConditionBatch:
    results: tuple[ConditionResult, ...]
    all_matched: bool
    any_matched: bool
    rule_limit_enforced: bool
    monitoring_started: bool
    notification_sent: bool


def _compare(value: float, operator: ConditionOperator, threshold: float) -> bool:
    if operator == ConditionOperator.GT:
        return value > threshold
    if operator == ConditionOperator.GTE:
        return value >= threshold
    if operator == ConditionOperator.LT:
        return value < threshold
    if operator == ConditionOperator.LTE:
        return value <= threshold
    if operator == ConditionOperator.EQ:
        return value == threshold
    if operator == ConditionOperator.NEQ:
        return value != threshold
    raise ValueError("unsupported_condition_operator")


def evaluate_conditions(
    metrics: Mapping[str, float],
    rules: Sequence[ConditionRule],
    *,
    max_rules: int = 64,
) -> ConditionBatch:
    cap = max(1, min(int(max_rules), 128))
    selected = tuple(rules[:cap])
    results: list[ConditionResult] = []

    seen: set[str] = set()
    for rule in selected:
        rule_id = str(rule.rule_id or "").strip()
        metric = str(rule.metric or "").strip()

        if not rule_id or rule_id in seen or not metric:
            results.append(
                ConditionResult(
                    rule_id=rule_id,
                    metric=metric,
                    boundary=ConditionBoundary.INVALID_RULE,
                    matched=False,
                    observed_value=None,
                    threshold=float(rule.threshold),
                    reason="rule_id_must_be_unique_and_metric_required",
                )
            )
            continue

        seen.add(rule_id)
        if metric not in metrics:
            results.append(
                ConditionResult(
                    rule_id=rule_id,
                    metric=metric,
                    boundary=ConditionBoundary.MISSING_METRIC,
                    matched=False,
                    observed_value=None,
                    threshold=float(rule.threshold),
                    reason="metric_not_available",
                )
            )
            continue

        observed = float(metrics[metric])
        threshold = float(rule.threshold)
        results.append(
            ConditionResult(
                rule_id=rule_id,
                metric=metric,
                boundary=ConditionBoundary.EVALUATED,
                matched=_compare(observed, rule.operator, threshold),
                observed_value=observed,
                threshold=threshold,
                reason="condition_evaluated",
            )
        )

    evaluated = tuple(results)
    valid_matches = [item.matched for item in evaluated if item.boundary == ConditionBoundary.EVALUATED]
    return ConditionBatch(
        results=evaluated,
        all_matched=bool(valid_matches) and all(valid_matches),
        any_matched=any(valid_matches),
        rule_limit_enforced=len(rules) <= cap,
        monitoring_started=False,
        notification_sent=False,
    )


def public_condition_batch(batch: ConditionBatch) -> dict[str, object]:
    return {
        "all_matched": batch.all_matched,
        "any_matched": batch.any_matched,
        "rule_limit_enforced": batch.rule_limit_enforced,
        "monitoring_started": batch.monitoring_started,
        "notification_sent": batch.notification_sent,
        "results": [
            {
                "rule_id": item.rule_id,
                "metric": item.metric,
                "boundary": item.boundary.value,
                "matched": item.matched,
                "observed_value": item.observed_value,
                "threshold": item.threshold,
                "reason": item.reason,
            }
            for item in batch.results
        ],
    }
