import importlib.util
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
    decision.DecisionCriterion("quality", 0.6, decision.CriterionDirection.BENEFIT),
    decision.DecisionCriterion("cost", 0.4, decision.CriterionDirection.COST),
)
options = (
    decision.DecisionOption("Premium", {"quality": 0.9, "cost": 0.8}),
    decision.DecisionOption("Value", {"quality": 0.7, "cost": 0.2}),
)
result = decision.analyze_decision(criteria, options, evidence_quality=0.9)
_assert(result.selected_option == "Value", f"cost direction must be inverted correctly: {result}")
_assert(result.ranked_options[0].name == "Value", "Value should rank first")
_assert(result.ranked_options[0].score > result.ranked_options[1].score, "selected option must have higher score")
print("benefit/cost weighted ranking: PASS")


constraint_result = decision.analyze_decision(
    criteria,
    (
        decision.DecisionOption("Allowed", {"quality": 0.75, "cost": 0.5}, hard_constraints_satisfied=True),
        decision.DecisionOption("Disallowed", {"quality": 1.0, "cost": 0.0}, hard_constraints_satisfied=False),
    ),
    evidence_quality=0.9,
)
_assert(constraint_result.selected_option == "Allowed", "hard constraints must disqualify otherwise superior options")
_assert(constraint_result.ranked_options[-1].disqualified is True, "disqualified option must remain visible but ineligible")
print("hard-constraint enforcement: PASS")


missing_result = decision.analyze_decision(
    criteria,
    (
        decision.DecisionOption("Incomplete", {"quality": 0.95}),
        decision.DecisionOption("Also incomplete", {"quality": 0.70}),
    ),
    evidence_quality=0.9,
)
_assert(missing_result.boundary == decision.DecisionBoundary.NEEDS_DATA, f"low coverage must require data: {missing_result}")
_assert(missing_result.overall_coverage < decision.MIN_DATA_COVERAGE, "missing-data boundary must reflect actual coverage")
_assert("cost" in missing_result.missing_criteria, "missing criterion must be public")
_assert(missing_result.confidence == decision.DecisionConfidence.LOW, "low coverage must keep confidence low")
print("missing-data decision boundary: PASS")


close_result = decision.analyze_decision(
    (
        decision.DecisionCriterion("a", 0.5),
        decision.DecisionCriterion("b", 0.5),
    ),
    (
        decision.DecisionOption("A", {"a": 0.8, "b": 0.6}),
        decision.DecisionOption("B", {"a": 0.75, "b": 0.64}),
    ),
    evidence_quality=0.9,
)
_assert(close_result.boundary == decision.DecisionBoundary.NO_CLEAR_WINNER, f"near-tie must not become a confident recommendation: {close_result}")
_assert(close_result.score_margin < decision.NO_CLEAR_WINNER_MARGIN, "near-tie margin must remain bounded")
print("no-clear-winner boundary: PASS")


sensitive_result = decision.analyze_decision(
    (
        decision.DecisionCriterion("performance", 0.55),
        decision.DecisionCriterion("simplicity", 0.45),
    ),
    (
        decision.DecisionOption("Fast", {"performance": 1.0, "simplicity": 0.0}),
        decision.DecisionOption("Simple", {"performance": 0.0, "simplicity": 1.0}),
    ),
    evidence_quality=0.95,
)
_assert(sensitive_result.selected_option == "Fast", "baseline winner should be Fast")
_assert(sensitive_result.sensitivity.stable is False, "reasonable criterion-weight variation should expose an unstable winner")
_assert(sensitive_result.sensitivity.winner_changes, "sensitivity result must identify at least one winner change")
_assert(sensitive_result.boundary == decision.DecisionBoundary.CONDITIONAL, f"unstable recommendation must be conditional: {sensitive_result}")
print("decision sensitivity boundary: PASS")


high_confidence = decision.analyze_decision(
    (
        decision.DecisionCriterion("reliability", 0.5),
        decision.DecisionCriterion("fit", 0.5),
    ),
    (
        decision.DecisionOption("Strong", {"reliability": 0.95, "fit": 0.95}),
        decision.DecisionOption("Weak", {"reliability": 0.45, "fit": 0.45}),
    ),
    evidence_quality=0.95,
)
_assert(high_confidence.boundary == decision.DecisionBoundary.RECOMMEND, f"strong stable evidence should permit recommendation: {high_confidence}")
_assert(high_confidence.confidence == decision.DecisionConfidence.HIGH, "strong stable evidence should produce HIGH confidence")
_assert(high_confidence.sensitivity.stable is True, "strong winner should remain stable")
print("high-confidence stable decision: PASS")


low_evidence = decision.analyze_decision(
    (
        decision.DecisionCriterion("reliability", 0.5),
        decision.DecisionCriterion("fit", 0.5),
    ),
    (
        decision.DecisionOption("Strong", {"reliability": 0.95, "fit": 0.95}),
        decision.DecisionOption("Weak", {"reliability": 0.45, "fit": 0.45}),
    ),
    evidence_quality=0.35,
)
_assert(low_evidence.selected_option == "Strong", "ranking can remain stable with low evidence")
_assert(low_evidence.confidence == decision.DecisionConfidence.LOW, "low evidence quality must cap decision confidence")
print("evidence-quality confidence cap: PASS")


feedback_base = (
    decision.DecisionCriterion("reliability", 0.5),
    decision.DecisionCriterion("cost", 0.5, decision.CriterionDirection.COST),
)
explicit_update = decision.apply_explicit_feedback(
    feedback_base,
    decision.DecisionFeedback(
        explicit=True,
        criterion_adjustments={"reliability": 0.10, "cost": -0.10},
        note="Reliability matters more for this decision.",
    ),
)
_assert(explicit_update.applied is True, f"explicit bounded feedback should apply: {explicit_update}")
learned_weights = {item.key: item.weight for item in explicit_update.criteria}
_assert(learned_weights["reliability"] > learned_weights["cost"], "explicit feedback should increase relative reliability weight")
_assert(abs(sum(learned_weights.values()) - 1.0) < 1e-6, "learned weights must remain normalized")
print("explicit bounded feedback learning: PASS")


implicit_update = decision.apply_explicit_feedback(
    feedback_base,
    decision.DecisionFeedback(
        explicit=False,
        criterion_adjustments={"reliability": 0.10},
        note="Inferred from behavior only.",
    ),
)
_assert(implicit_update.applied is False, "implicit feedback must never silently change decision weights")
_assert(implicit_update.reason == "implicit_feedback_rejected", "implicit rejection reason must be explicit")
print("implicit learning rejected: PASS")


empty_explicit = decision.apply_explicit_feedback(
    feedback_base,
    decision.DecisionFeedback(explicit=True, criterion_adjustments={}),
)
_assert(empty_explicit.applied is False, "explicit feedback without an explicit adjustment must not mutate weights")
_assert(empty_explicit.reason == "no_explicit_weight_adjustments", "empty explicit feedback reason mismatch")
print("empty learning signal rejected: PASS")


out_of_bounds = decision.apply_explicit_feedback(
    feedback_base,
    decision.DecisionFeedback(explicit=True, criterion_adjustments={"reliability": 0.25}),
)
_assert(out_of_bounds.applied is False, "weight changes beyond the bounded limit must be rejected")
_assert(out_of_bounds.reason == "weight_adjustment_out_of_bounds", "out-of-bounds reason mismatch")
print("learning adjustment bound: PASS")


unknown = decision.apply_explicit_feedback(
    feedback_base,
    decision.DecisionFeedback(explicit=True, criterion_adjustments={"unknown": 0.10}),
)
_assert(unknown.applied is False, "unknown criteria must not be learned")
_assert(unknown.reason.startswith("unknown_criteria:"), "unknown criterion rejection reason mismatch")
print("unknown learning criterion rejected: PASS")


first = decision.analyze_decision(criteria, options, evidence_quality=0.9)
second = decision.analyze_decision(criteria, options, evidence_quality=0.9)
_assert(first == second, "decision analysis must be deterministic for identical inputs")
print("deterministic decision analysis: PASS")


empty_result = decision.analyze_decision(
    (decision.DecisionCriterion("fit", 1.0),),
    (),
    evidence_quality=0.8,
)
_assert(empty_result.selected_option is None, "empty option set must not fabricate a selection")
_assert(empty_result.boundary == decision.DecisionBoundary.NEEDS_DATA, "empty option set must require data")
print("empty decision set safe behavior: PASS")


public = decision.public_decision_metadata(high_confidence)
_assert(public["selected_option"] == "Strong", "public decision metadata must expose the selected option")
_assert(public["boundary"] == "RECOMMEND", "public decision metadata must expose the decision boundary")
_assert(public["confidence"] == "HIGH", "public decision metadata must expose confidence")
_assert("winner_changes" not in public["sensitivity"], "public metadata should expose sensitivity count, not internal variation details")
print("public decision metadata privacy: PASS")


print("SHY v0.21 LEARNING & DECISION CHECKPOINT 1: PASS")
