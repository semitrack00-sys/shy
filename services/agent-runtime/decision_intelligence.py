from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


class CriterionDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


class DecisionBoundary(str, Enum):
    DECIDE = "DECIDE"
    DATA_REQUIRED = "DATA_REQUIRED"
    NO_ELIGIBLE_STRATEGY = "NO_ELIGIBLE_STRATEGY"
    VERIFY_OUTCOME_REQUIRED = "VERIFY_OUTCOME_REQUIRED"


class OutcomeVerification(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    CORRECTED = "CORRECTED"


@dataclass(frozen=True)
class DecisionCriterion:
    name: str
    weight: float
    direction: CriterionDirection = CriterionDirection.HIGHER_IS_BETTER
    required: bool = True


@dataclass(frozen=True)
class StrategyOption:
    name: str
    metrics: Mapping[str, float]
    evidence_quality: float = 0.7
    hard_constraints_satisfied: bool = True


@dataclass(frozen=True)
class StrategyScore:
    name: str
    score: float
    criterion_scores: tuple[tuple[str, float], ...]
    evidence_quality: float
    eligible: bool
    missing_required: tuple[str, ...]


@dataclass(frozen=True)
class DecisionRecommendation:
    selected: StrategyScore | None
    ranked: tuple[StrategyScore, ...]
    boundary: DecisionBoundary
    confidence: float
    score_margin: float
    tied: bool
    missing_required: tuple[str, ...]


@dataclass(frozen=True)
class DecisionScenario:
    name: str
    probability: float
    option_metric_deltas: Mapping[str, Mapping[str, float]]


@dataclass(frozen=True)
class ScenarioScore:
    scenario: str
    probability: float
    score: float


@dataclass(frozen=True)
class StrategySimulation:
    strategy: str
    expected_score: float
    best_case_score: float
    worst_case_score: float
    scenario_scores: tuple[ScenarioScore, ...]


@dataclass(frozen=True)
class SimulationRecommendation:
    selected_strategy: str | None
    ranked: tuple[StrategySimulation, ...]
    confidence: float
    bounded: bool


@dataclass(frozen=True)
class VerifiedOutcome:
    decision_id: str
    strategy_name: str
    target_criterion: str
    predicted_score: float
    observed_score: float
    verification: OutcomeVerification
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class LearningPolicy:
    learning_rate: float = 0.20
    max_weight_delta: float = 0.05
    min_evidence_items: int = 1


@dataclass(frozen=True)
class LearningSignal:
    accepted: bool
    decision_id: str
    target_criterion: str
    delta: float
    verification: OutcomeVerification
    reason: str


@dataclass(frozen=True)
class LearningApplication:
    applied: bool
    weights: tuple[tuple[str, float], ...]
    target_criterion: str
    requested_delta: float
    applied_delta: float
    reason: str


_PROTECTED_LEARNING_MARKERS = (
    "security",
    "permission",
    "approval",
    "privacy",
    "secret",
    "credential",
    "authorization",
    "authentication",
    "tool policy",
    "tool_policy",
    "safety",
    "guardrail",
    "rate limit",
    "rate_limit",
)


def _bounded_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalized_name(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _normalized_weights(criteria: Sequence[DecisionCriterion]) -> dict[str, float]:
    if not criteria:
        raise ValueError("At least one decision criterion is required.")

    seen: set[str] = set()
    total = 0.0
    raw: dict[str, float] = {}
    for criterion in criteria:
        name = str(criterion.name or "").strip()
        if not name:
            raise ValueError("Decision criterion names must be non-empty.")
        key = _normalized_name(name)
        if key in seen:
            raise ValueError(f"Duplicate decision criterion: {name}")
        seen.add(key)
        weight = max(0.0, float(criterion.weight))
        raw[name] = weight
        total += weight

    if total <= 0:
        equal = 1.0 / len(raw)
        return {name: equal for name in raw}

    return {name: weight / total for name, weight in raw.items()}


def _criterion_value(
    option: StrategyOption,
    criterion: DecisionCriterion,
) -> tuple[float | None, bool]:
    if criterion.name not in option.metrics:
        return None, criterion.required

    raw = _bounded_unit(float(option.metrics[criterion.name]))
    if criterion.direction == CriterionDirection.LOWER_IS_BETTER:
        raw = 1.0 - raw
    return raw, False


def score_strategy(
    option: StrategyOption,
    criteria: Sequence[DecisionCriterion],
) -> StrategyScore:
    weights = _normalized_weights(criteria)
    contributions: list[tuple[str, float]] = []
    missing_required: list[str] = []
    score = 0.0

    for criterion in criteria:
        value, missing = _criterion_value(option, criterion)
        if missing:
            missing_required.append(criterion.name)
            contributions.append((criterion.name, 0.0))
            continue
        if value is None:
            # Optional missing values are neutral rather than silently optimistic.
            value = 0.5
        contribution = value * weights[criterion.name]
        score += contribution
        contributions.append((criterion.name, round(contribution, 6)))

    eligible = bool(option.hard_constraints_satisfied) and not missing_required
    return StrategyScore(
        name=option.name,
        score=round(_bounded_unit(score), 6),
        criterion_scores=tuple(contributions),
        evidence_quality=round(_bounded_unit(option.evidence_quality), 6),
        eligible=eligible,
        missing_required=tuple(sorted(missing_required)),
    )


def compare_strategies(
    options: Sequence[StrategyOption],
    criteria: Sequence[DecisionCriterion],
) -> DecisionRecommendation:
    if not options:
        return DecisionRecommendation(
            selected=None,
            ranked=(),
            boundary=DecisionBoundary.DATA_REQUIRED,
            confidence=0.0,
            score_margin=0.0,
            tied=False,
            missing_required=(),
        )

    scored = tuple(score_strategy(option, criteria) for option in options)
    eligible = sorted(
        (item for item in scored if item.eligible),
        key=lambda item: (-item.score, item.name.lower()),
    )

    missing_required = tuple(
        sorted({name for item in scored for name in item.missing_required})
    )

    if not eligible:
        boundary = (
            DecisionBoundary.DATA_REQUIRED
            if missing_required
            else DecisionBoundary.NO_ELIGIBLE_STRATEGY
        )
        return DecisionRecommendation(
            selected=None,
            ranked=tuple(sorted(scored, key=lambda item: (-item.score, item.name.lower()))),
            boundary=boundary,
            confidence=0.0,
            score_margin=0.0,
            tied=False,
            missing_required=missing_required,
        )

    selected = eligible[0]
    runner_up = eligible[1] if len(eligible) > 1 else None
    margin = selected.score - runner_up.score if runner_up else selected.score
    tied = bool(runner_up and abs(margin) < 1e-9)

    # Confidence is intentionally conservative: evidence quality is the ceiling,
    # while larger score separation can increase confidence only within that ceiling.
    evidence_ceiling = min(item.evidence_quality for item in eligible[:2]) if runner_up else selected.evidence_quality
    separation_component = min(1.0, 0.55 + max(0.0, margin) * 1.5)
    confidence = min(evidence_ceiling, separation_component)
    if tied:
        confidence = min(confidence, 0.5)

    return DecisionRecommendation(
        selected=selected,
        ranked=tuple(eligible),
        boundary=DecisionBoundary.DECIDE,
        confidence=round(_bounded_unit(confidence), 6),
        score_margin=round(max(0.0, margin), 6),
        tied=tied,
        missing_required=missing_required,
    )


def simulate_strategies(
    options: Sequence[StrategyOption],
    criteria: Sequence[DecisionCriterion],
    scenarios: Sequence[DecisionScenario],
    *,
    max_scenarios: int = 12,
) -> SimulationRecommendation:
    if not options or not scenarios:
        return SimulationRecommendation(
            selected_strategy=None,
            ranked=(),
            confidence=0.0,
            bounded=True,
        )

    bounded_scenarios = tuple(scenarios[: max(1, int(max_scenarios))])
    probability_total = sum(max(0.0, float(item.probability)) for item in bounded_scenarios)
    if probability_total <= 0:
        raise ValueError("Scenario probabilities must contain positive mass.")

    simulations: list[StrategySimulation] = []
    for option in options:
        scores: list[ScenarioScore] = []
        for scenario in bounded_scenarios:
            probability = max(0.0, float(scenario.probability)) / probability_total
            deltas = scenario.option_metric_deltas.get(option.name, {})
            adjusted_metrics = dict(option.metrics)
            for criterion_name, delta in deltas.items():
                current = float(adjusted_metrics.get(criterion_name, 0.5))
                adjusted_metrics[criterion_name] = _bounded_unit(current + float(delta))

            adjusted = StrategyOption(
                name=option.name,
                metrics=adjusted_metrics,
                evidence_quality=option.evidence_quality,
                hard_constraints_satisfied=option.hard_constraints_satisfied,
            )
            scored = score_strategy(adjusted, criteria)
            scenario_score = scored.score if scored.eligible else 0.0
            scores.append(
                ScenarioScore(
                    scenario=scenario.name,
                    probability=round(probability, 6),
                    score=round(scenario_score, 6),
                )
            )

        expected = sum(item.probability * item.score for item in scores)
        simulations.append(
            StrategySimulation(
                strategy=option.name,
                expected_score=round(expected, 6),
                best_case_score=round(max(item.score for item in scores), 6),
                worst_case_score=round(min(item.score for item in scores), 6),
                scenario_scores=tuple(scores),
            )
        )

    ranked = tuple(
        sorted(
            simulations,
            key=lambda item: (
                -item.expected_score,
                -item.worst_case_score,
                item.strategy.lower(),
            ),
        )
    )
    selected = ranked[0] if ranked else None
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = (
        selected.expected_score - runner_up.expected_score
        if selected and runner_up
        else (selected.expected_score if selected else 0.0)
    )
    confidence = min(0.9, 0.55 + max(0.0, margin))
    if selected and runner_up and abs(margin) < 1e-9:
        confidence = min(confidence, 0.5)

    return SimulationRecommendation(
        selected_strategy=selected.strategy if selected else None,
        ranked=ranked,
        confidence=round(_bounded_unit(confidence), 6),
        bounded=len(scenarios) <= max(1, int(max_scenarios)),
    )


def is_learning_target_protected(target: str) -> bool:
    normalized = _normalized_name(target)
    return any(marker in normalized for marker in _PROTECTED_LEARNING_MARKERS)


def derive_learning_signal(
    outcome: VerifiedOutcome,
    *,
    policy: LearningPolicy | None = None,
) -> LearningSignal:
    active_policy = policy or LearningPolicy()
    target = str(outcome.target_criterion or "").strip()

    if not target:
        return LearningSignal(
            accepted=False,
            decision_id=outcome.decision_id,
            target_criterion=target,
            delta=0.0,
            verification=outcome.verification,
            reason="missing_target_criterion",
        )

    if is_learning_target_protected(target):
        return LearningSignal(
            accepted=False,
            decision_id=outcome.decision_id,
            target_criterion=target,
            delta=0.0,
            verification=outcome.verification,
            reason="protected_learning_target",
        )

    if outcome.verification not in {OutcomeVerification.VERIFIED, OutcomeVerification.CORRECTED}:
        return LearningSignal(
            accepted=False,
            decision_id=outcome.decision_id,
            target_criterion=target,
            delta=0.0,
            verification=outcome.verification,
            reason="verified_outcome_required",
        )

    if len(tuple(item for item in outcome.evidence_ids if str(item).strip())) < max(1, int(active_policy.min_evidence_items)):
        return LearningSignal(
            accepted=False,
            decision_id=outcome.decision_id,
            target_criterion=target,
            delta=0.0,
            verification=outcome.verification,
            reason="verified_evidence_required",
        )

    prediction_error = _bounded_unit(outcome.observed_score) - _bounded_unit(outcome.predicted_score)
    raw_delta = prediction_error * max(0.0, float(active_policy.learning_rate))
    limit = max(0.0, float(active_policy.max_weight_delta))
    bounded_delta = max(-limit, min(limit, raw_delta))

    return LearningSignal(
        accepted=True,
        decision_id=outcome.decision_id,
        target_criterion=target,
        delta=round(bounded_delta, 6),
        verification=outcome.verification,
        reason="verified_outcome_learning",
    )


def apply_learning_signal(
    weights: Mapping[str, float],
    signal: LearningSignal,
) -> LearningApplication:
    ordered_names = tuple(sorted(str(name) for name in weights))
    current = {name: max(0.0, float(weights[name])) for name in ordered_names}

    if not signal.accepted:
        return LearningApplication(
            applied=False,
            weights=tuple((name, round(value, 6)) for name, value in current.items()),
            target_criterion=signal.target_criterion,
            requested_delta=signal.delta,
            applied_delta=0.0,
            reason=signal.reason,
        )

    if is_learning_target_protected(signal.target_criterion):
        return LearningApplication(
            applied=False,
            weights=tuple((name, round(value, 6)) for name, value in current.items()),
            target_criterion=signal.target_criterion,
            requested_delta=signal.delta,
            applied_delta=0.0,
            reason="protected_learning_target",
        )

    matching_name = next(
        (name for name in ordered_names if _normalized_name(name) == _normalized_name(signal.target_criterion)),
        None,
    )
    if matching_name is None:
        return LearningApplication(
            applied=False,
            weights=tuple((name, round(value, 6)) for name, value in current.items()),
            target_criterion=signal.target_criterion,
            requested_delta=signal.delta,
            applied_delta=0.0,
            reason="unknown_learning_target",
        )

    before = current[matching_name]
    current[matching_name] = max(0.0, before + float(signal.delta))
    total = sum(current.values())
    if total <= 0:
        return LearningApplication(
            applied=False,
            weights=tuple((name, round(value, 6)) for name, value in current.items()),
            target_criterion=signal.target_criterion,
            requested_delta=signal.delta,
            applied_delta=0.0,
            reason="invalid_weight_state",
        )

    normalized = {name: value / total for name, value in current.items()}
    applied_delta = normalized[matching_name] - (
        before / max(sum(max(0.0, float(weights[name])) for name in ordered_names), 1e-12)
    )

    return LearningApplication(
        applied=True,
        weights=tuple((name, round(value, 6)) for name, value in normalized.items()),
        target_criterion=matching_name,
        requested_delta=signal.delta,
        applied_delta=round(applied_delta, 6),
        reason="verified_learning_applied",
    )


def public_decision_metadata(
    recommendation: DecisionRecommendation,
) -> dict[str, object]:
    return {
        "decision_boundary": recommendation.boundary.value,
        "selected_strategy": recommendation.selected.name if recommendation.selected else None,
        "confidence": recommendation.confidence,
        "score_margin": recommendation.score_margin,
        "tied": recommendation.tied,
        "missing_required": list(recommendation.missing_required),
        "ranked_strategies": [
            {
                "name": item.name,
                "score": item.score,
                "evidence_quality": item.evidence_quality,
                "eligible": item.eligible,
            }
            for item in recommendation.ranked
        ],
    }


def public_learning_metadata(
    signal: LearningSignal,
) -> dict[str, object]:
    return {
        "accepted": signal.accepted,
        "decision_id": signal.decision_id,
        "target_criterion": signal.target_criterion,
        "delta": signal.delta if signal.accepted else 0.0,
        "verification": signal.verification.value,
        "reason": signal.reason,
    }
