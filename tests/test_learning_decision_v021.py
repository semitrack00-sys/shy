import importlib.util
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "services" / "agent-runtime" / "decision_intelligence.py"

spec = importlib.util.spec_from_file_location("shy_decision_intelligence_v021", MODULE_PATH)
decision = importlib.util.module_from_spec(spec)
sys.modules["shy_decision_intelligence_v021"] = decision
spec.loader.exec_module(decision)


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


criteria = (
    decision.DecisionCriterion("correctness", 0.30),
    decision.DecisionCriterion("feasibility", 0.20),
    decision.DecisionCriterion("evidence", 0.20),
    decision.DecisionCriterion("cost", 0.10, decision.CriterionDirection.LOWER_IS_BETTER),
    decision.DecisionCriterion("risk", 0.10, decision.CriterionDirection.LOWER_IS_BETTER),
    decision.DecisionCriterion("expected_outcome", 0.10),
)

options = (
    decision.StrategyOption(
        "strategy_a",
        {
            "correctness": 0.78,
            "feasibility": 0.92,
            "evidence": 0.66,
            "cost": 0.25,
            "risk": 0.42,
            "expected_outcome": 0.72,
        },
        evidence_quality=0.82,
    ),
    decision.StrategyOption(
        "strategy_b",
        {
            "correctness": 0.92,
            "feasibility": 0.84,
            "evidence": 0.88,
            "cost": 0.38,
            "risk": 0.22,
            "expected_outcome": 0.90,
        },
        evidence_quality=0.93,
    ),
    decision.StrategyOption(
        "strategy_c",
        {
            "correctness": 0.70,
            "feasibility": 0.95,
            "evidence": 0.58,
            "cost": 0.12,
            "risk": 0.55,
            "expected_outcome": 0.65,
        },
        evidence_quality=0.74,
    ),
)

comparison = decision.compare_strategies(options, criteria)
_assert(comparison.boundary == decision.DecisionBoundary.DECIDE, "complete strategies should be decidable")
_assert(comparison.selected is not None, "decision comparison must select a strategy")
_assert(comparison.selected.name == "strategy_b", f"expected strategy_b, got {comparison.selected}")
_assert(comparison.ranked[0].score > comparison.ranked[1].score, "ranking must be deterministic by weighted score")
_assert(0.0 < comparison.confidence <= comparison.selected.evidence_quality, "confidence must be bounded by evidence")
print("weighted strategy comparison: PASS")


blocked = decision.StrategyOption(
    "unsafe_fast_option",
    {
        "correctness": 1.0,
        "feasibility": 1.0,
        "evidence": 1.0,
        "cost": 0.0,
        "risk": 0.0,
        "expected_outcome": 1.0,
    },
    evidence_quality=1.0,
    hard_constraints_satisfied=False,
)
constraint_comparison = decision.compare_strategies((blocked, options[1]), criteria)
_assert(constraint_comparison.selected is not None, "an eligible strategy should still be selected")
_assert(constraint_comparison.selected.name == "strategy_b", "hard-constraint failure must disqualify the higher raw score")
_assert(all(row.name != "unsafe_fast_option" for row in constraint_comparison.ranked), "ineligible strategy must not enter eligible ranking")
print("hard constraint enforcement: PASS")


missing = decision.StrategyOption(
    "missing_evidence",
    {
        "correctness": 0.9,
        "feasibility": 0.9,
        "cost": 0.2,
        "risk": 0.2,
        "expected_outcome": 0.9,
    },
)
missing_only = decision.compare_strategies((missing,), criteria)
_assert(missing_only.selected is None, "required missing metric must prevent selection")
_assert(missing_only.boundary == decision.DecisionBoundary.DATA_REQUIRED, "required missing data must surface DATA_REQUIRED")
_assert("evidence" in missing_only.missing_required, "missing criterion must be public and explicit")
print("missing decision data boundary: PASS")


tie_criteria = (
    decision.DecisionCriterion("quality", 1.0),
)
tie = decision.compare_strategies(
    (
        decision.StrategyOption("Beta", {"quality": 0.8}, evidence_quality=0.9),
        decision.StrategyOption("Alpha", {"quality": 0.8}, evidence_quality=0.9),
    ),
    tie_criteria,
)
_assert(tie.selected is not None and tie.selected.name == "Alpha", "ties must resolve deterministically by name")
_assert(tie.tied is True, "equal scores must be reported as tied")
_assert(tie.confidence <= 0.5, "tie confidence must remain conservative")
print("stable tie handling: PASS")


simulation_scenarios = (
    decision.DecisionScenario(
        "normal",
        0.55,
        {
            "strategy_a": {},
            "strategy_b": {},
            "strategy_c": {},
        },
    ),
    decision.DecisionScenario(
        "cost_pressure",
        0.25,
        {
            "strategy_a": {"cost": 0.10},
            "strategy_b": {"cost": 0.30},
            "strategy_c": {"cost": 0.05},
        },
    ),
    decision.DecisionScenario(
        "reliability_stress",
        0.20,
        {
            "strategy_a": {"risk": 0.12, "correctness": -0.08},
            "strategy_b": {"risk": 0.05, "correctness": -0.02},
            "strategy_c": {"risk": 0.20, "correctness": -0.12},
        },
    ),
)
simulation = decision.simulate_strategies(options, criteria, simulation_scenarios)
_assert(simulation.selected_strategy == "strategy_b", f"simulation should preserve robust strategy_b selection: {simulation}")
_assert(len(simulation.ranked) == 3, "all strategies must be simulated")
_assert(all(len(item.scenario_scores) == 3 for item in simulation.ranked), "each strategy must have all scenario scores")
_assert(all(item.worst_case_score <= item.expected_score <= item.best_case_score for item in simulation.ranked), "simulation summary must stay internally consistent")
print("bounded scenario simulation: PASS")


many_scenarios = tuple(
    decision.DecisionScenario(
        f"scenario-{index}",
        1.0,
        {"strategy_b": {"risk": min(0.2, index * 0.001)}},
    )
    for index in range(30)
)
bounded_simulation = decision.simulate_strategies((options[1],), criteria, many_scenarios, max_scenarios=12)
_assert(len(bounded_simulation.ranked[0].scenario_scores) == 12, "simulation must enforce max_scenarios")
_assert(bounded_simulation.bounded is False, "metadata must report that the original request exceeded the bound")
print("simulation hard bound: PASS")


unverified = decision.VerifiedOutcome(
    decision_id="decision-001",
    strategy_name="strategy_b",
    target_criterion="expected_outcome",
    predicted_score=0.80,
    observed_score=0.95,
    verification=decision.OutcomeVerification.UNVERIFIED,
    evidence_ids=("result-1",),
)
unverified_signal = decision.derive_learning_signal(unverified)
_assert(unverified_signal.accepted is False, "unverified outcomes must never produce learning")
_assert(unverified_signal.reason == "verified_outcome_required", "unverified rejection reason must be explicit")
print("unverified learning rejection: PASS")


verified = decision.VerifiedOutcome(
    decision_id="decision-002",
    strategy_name="strategy_b",
    target_criterion="expected_outcome",
    predicted_score=0.70,
    observed_score=0.95,
    verification=decision.OutcomeVerification.VERIFIED,
    evidence_ids=("verified-result-1",),
)
verified_signal = decision.derive_learning_signal(
    verified,
    policy=decision.LearningPolicy(learning_rate=0.50, max_weight_delta=0.05),
)
_assert(verified_signal.accepted is True, "verified evidence-backed outcome should produce learning")
_assert(0.0 < verified_signal.delta <= 0.05, "verified learning delta must be positive and hard-bounded")
print("verified outcome learning signal: PASS")


corrected = decision.VerifiedOutcome(
    decision_id="decision-003",
    strategy_name="strategy_a",
    target_criterion="cost",
    predicted_score=0.80,
    observed_score=0.40,
    verification=decision.OutcomeVerification.CORRECTED,
    evidence_ids=("correction-1",),
)
corrected_signal = decision.derive_learning_signal(
    corrected,
    policy=decision.LearningPolicy(learning_rate=0.50, max_weight_delta=0.05),
)
_assert(corrected_signal.accepted is True, "verified correction should be learnable")
_assert(-0.05 <= corrected_signal.delta < 0.0, "correction learning must remain bounded")
print("verified correction learning signal: PASS")


no_evidence = decision.VerifiedOutcome(
    decision_id="decision-004",
    strategy_name="strategy_b",
    target_criterion="expected_outcome",
    predicted_score=0.70,
    observed_score=0.90,
    verification=decision.OutcomeVerification.VERIFIED,
    evidence_ids=(),
)
no_evidence_signal = decision.derive_learning_signal(no_evidence)
_assert(no_evidence_signal.accepted is False, "verified label without evidence must not learn")
_assert(no_evidence_signal.reason == "verified_evidence_required", "evidence requirement must be explicit")
print("verified-evidence requirement: PASS")


for protected_target in (
    "security",
    "tool_policy",
    "approval rules",
    "privacy policy",
    "permission level",
    "authorization guardrail",
):
    protected_outcome = decision.VerifiedOutcome(
        decision_id="decision-protected",
        strategy_name="strategy_b",
        target_criterion=protected_target,
        predicted_score=0.2,
        observed_score=1.0,
        verification=decision.OutcomeVerification.VERIFIED,
        evidence_ids=("verified-security-result",),
    )
    protected_signal = decision.derive_learning_signal(protected_outcome)
    _assert(protected_signal.accepted is False, f"protected target must never learn: {protected_target}")
    _assert(protected_signal.reason == "protected_learning_target", f"protected target reason mismatch: {protected_target}")
print("security and permission learning protection: PASS")


base_weights = {
    "correctness": 0.30,
    "feasibility": 0.20,
    "evidence": 0.20,
    "cost": 0.10,
    "risk": 0.10,
    "expected_outcome": 0.10,
}
application = decision.apply_learning_signal(base_weights, verified_signal)
_assert(application.applied is True, "accepted learning signal should apply to known criterion")
applied = dict(application.weights)
_assert(math.isclose(sum(applied.values()), 1.0, rel_tol=0.0, abs_tol=2e-6), "learned decision weights must remain normalized")
_assert(applied["expected_outcome"] > base_weights["expected_outcome"], "positive verified outcome should increase target weight")
_assert(abs(application.requested_delta) <= 0.05, "requested learning delta must remain bounded")
print("bounded normalized learning application: PASS")


rejected_application = decision.apply_learning_signal(base_weights, unverified_signal)
_assert(rejected_application.applied is False, "rejected signal must not mutate weights")
_assert(dict(rejected_application.weights) == base_weights, "unverified signal must leave weights unchanged")
print("rejected learning is non-mutating: PASS")


decision_metadata = decision.public_decision_metadata(comparison)
_assert(decision_metadata["selected_strategy"] == "strategy_b", "public decision metadata must expose selected strategy")
_assert(decision_metadata["decision_boundary"] == "DECIDE", "public decision boundary mismatch")
_assert("criterion_scores" not in decision_metadata, "public metadata should not expose internal scoring traces")
print("public decision metadata: PASS")


learning_metadata = decision.public_learning_metadata(verified_signal)
_assert(learning_metadata["accepted"] is True, "public learning metadata should expose acceptance")
_assert(learning_metadata["verification"] == "VERIFIED", "public learning metadata should expose verification class")
_assert("evidence_ids" not in learning_metadata, "public learning metadata must not expose evidence identifiers")
print("public learning metadata: PASS")


print("SHY v0.21 LEARNING & DECISION CHECKPOINT 1: PASS")
