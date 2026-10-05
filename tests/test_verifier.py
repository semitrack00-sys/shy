import importlib.util
from pathlib import Path
from types import SimpleNamespace


root = Path(__file__).resolve().parents[1]
verifier_path = root / "services" / "agent-runtime" / "verifier.py"
loop_state_path = root / "services" / "agent-runtime" / "loop_state.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verifier_module = load_module("shy_verifier_test", verifier_path)
loop_module = load_module("shy_loop_state_for_verifier_test", loop_state_path)

PlanStep = loop_module.PlanStep
PlanStepStatus = loop_module.PlanStepStatus
ActionType = loop_module.ActionType

verify_task_result = verifier_module.verify_task_result
VerificationOutcome = verifier_module.VerificationOutcome
DefectType = verifier_module.DefectType


def make_task(plan_steps, research_sources=None):
    return SimpleNamespace(
        plan_steps=plan_steps,
        research_sources=research_sources or [],
    )


passed = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.REASON,
                objective="Provide response",
                status=PlanStepStatus.EXECUTED,
                result_summary="General recommendation.",
            )
        ]
    )
)
assert passed.outcome == VerificationOutcome.PASS
print("verified complete result: PASS")


unsupported = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.REASON,
                objective="Provide current facts",
                status=PlanStepStatus.EXECUTED,
                result_summary="Latest market share is 50%.",
            )
        ]
    )
)
assert DefectType.MISSING_EVIDENCE in unsupported.issues
assert unsupported.outcome in (
    VerificationOutcome.CORRECTABLE,
    VerificationOutcome.FAIL,
)
print("unsupported claim detection: PASS")


valid_citation = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.REASON,
                objective="Summarize sources",
                status=PlanStepStatus.EXECUTED,
                result_summary="The report confirms this [1].",
            )
        ],
        research_sources=[
            {
                "number": 1,
                "url": "https://example.com/source",
                "supports_claim_ids": ["claim-1"],
            }
        ],
    )
)
assert not valid_citation.citation_issues
print("valid citation accepted: PASS")


invalid_citation = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.REASON,
                objective="Summarize sources",
                status=PlanStepStatus.EXECUTED,
                result_summary="The report confirms this [3].",
            )
        ],
        research_sources=[
            {
                "number": 1,
                "url": "https://example.com/source",
                "supports_claim_ids": ["claim-1"],
            }
        ],
    )
)
assert any(issue.defect == DefectType.CITATION_INVALID for issue in invalid_citation.citation_issues)
print("nonexistent citation detection: PASS")


mismatch_citation = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.REASON,
                objective="Summarize sources",
                status=PlanStepStatus.EXECUTED,
                result_summary="The report confirms this [1].",
            )
        ],
        research_sources=[
            {
                "number": 1,
                "url": "ftp://invalid-url",
                "supports_claim_ids": ["claim-1"],
            }
        ],
    )
)
assert any(issue.defect == DefectType.CITATION_MISMATCH for issue in mismatch_citation.citation_issues)
print("citation/source mismatch detection: PASS")


contradiction = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.REASON,
                objective="Summarize sources",
                status=PlanStepStatus.EXECUTED,
                result_summary="The report confirms this [1] [2].",
            )
        ],
        research_sources=[
            {
                "number": 1,
                "url": "https://example.com/a",
                "supports_claim_ids": ["claim-1"],
            },
            {
                "number": 2,
                "url": "https://example.com/b",
                "contradicts_claim_ids": ["claim-1"],
            },
        ],
    )
)
assert DefectType.CONTRADICTORY_EVIDENCE in contradiction.issues
print("contradictory evidence detection: PASS")


tool_mismatch = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.TOOL,
                objective="Check health",
                status=PlanStepStatus.EXECUTED,
                tool_name="system.health",
                result_summary="status=TOOL_RESULT;tool=web.search;tool_status=EXECUTED",
            )
        ]
    )
)
assert DefectType.TOOL_RESULT_MISMATCH in tool_mismatch.issues
print("tool-result mismatch detection: PASS")


incomplete = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.TOOL,
                objective="Check health",
                status=PlanStepStatus.EXECUTED,
                tool_name="system.health",
                result_summary="",
            )
        ]
    )
)
assert DefectType.INCOMPLETE_RESULT in incomplete.issues
print("incomplete result detection: PASS")


det1 = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.REASON,
                objective="Stable summary",
                status=PlanStepStatus.EXECUTED,
                result_summary="Stable summary [1].",
            )
        ],
        research_sources=[
            {
                "number": 1,
                "url": "https://example.com/one",
                "supports_claim_ids": ["claim-1"],
            }
        ],
    )
)
det2 = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.REASON,
                objective="Stable summary",
                status=PlanStepStatus.EXECUTED,
                result_summary="Stable summary [1].",
            )
        ],
        research_sources=[
            {
                "number": 1,
                "url": "https://example.com/one",
                "supports_claim_ids": ["claim-1"],
            }
        ],
    )
)
assert det1.to_public_dict() == det2.to_public_dict()
print("deterministic verification report: PASS")


def fake_semantic_verifier(claims, evidence, task_state):
    assert isinstance(claims, list)
    assert isinstance(evidence, list)
    assert task_state is not None
    return {
        "issues": ["UNSUPPORTED_CLAIM"],
    }


semantic = verify_task_result(
    make_task(
        [
            PlanStep(
                step_id=1,
                action_type=ActionType.REASON,
                objective="Stable summary",
                status=PlanStepStatus.EXECUTED,
                result_summary="A claim.",
            )
        ]
    ),
    semantic_verifier=fake_semantic_verifier,
)
assert DefectType.UNSUPPORTED_CLAIM in semantic.issues
print("semantic verifier injection: PASS")


public_report = semantic.to_public_dict()
forbidden = (
    "chain_of_thought",
    "scratchpad",
    "internal_monologue",
    "reasoning_trace",
    "hidden_reasoning",
)
for field in forbidden:
    assert field not in public_report
print("no private reasoning fields: PASS")


assert not hasattr(verifier_module, "httpx")
print("verifier is provider-independent: PASS")

print("SHY Phase 3 verifier tests: PASS")
