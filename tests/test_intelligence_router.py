import importlib.util
from pathlib import Path


root = Path(__file__).resolve().parents[1]
router_path = root / "services" / "agent-runtime" / "intelligence_router.py"
types_path = root / "services" / "core" / "intelligence_types.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


router_module = load_module("shy_intelligence_router", router_path)
types_module = load_module("shy_intelligence_types_test", types_path)

IntelligenceRouter = router_module.IntelligenceRouter
Capability = types_module.Capability
CodingTaskType = types_module.CodingTaskType
ReasonCode = types_module.ReasonCode

router = IntelligenceRouter()

chat = router.analyze("Hello SHY")
assert chat.primary_capability == Capability.CHAT
assert chat.reason_code == ReasonCode.SIMPLE_CONVERSATION
print("chat classification: PASS")

reasoning = router.analyze("Explain photosynthesis")
assert reasoning.primary_capability in (Capability.CHAT, Capability.REASONING)
print("reasoning/chat flexibility: PASS")

research = router.analyze("Research the latest developments in battery technology")
assert research.primary_capability == Capability.RESEARCH
assert research.requires_external_evidence is True
assert research.requires_tool is True
print("research classification: PASS")

multi_step = router.analyze(
    "Compare these five constraints and develop a multi-stage implementation plan"
)
assert multi_step.primary_capability == Capability.MULTI_STEP
print("multi-step classification: PASS")

web_search = router.analyze("Search the web for transformer architecture updates")
assert web_search.primary_capability == Capability.RESEARCH
print("search classification: PASS")

tool_request = router.analyze("Use system health")
assert tool_request.primary_capability == Capability.TOOL
assert tool_request.requires_tool is True
print("explicit tool classification: PASS")

coding = router.analyze("Fix this Python function that crashes on empty input")
assert coding.primary_capability == Capability.CODING
assert coding.coding_profile is not None
assert coding.coding_profile.task_type in (CodingTaskType.DEBUG_EXCEPTION, CodingTaskType.UNKNOWN)
assert coding.verification_required is True
print("coding classification: PASS")

false_positive = router.analyze("What is the dress code for this event?")
assert false_positive.primary_capability != Capability.CODING
medical_false_positive = router.analyze("Explain this medical billing code")
assert medical_false_positive.primary_capability == Capability.CHAT
print("coding false-positive protection: PASS")

first = router.analyze("Research hybrid battery chemistry")
second = router.analyze("Research hybrid battery chemistry")
assert first == second
print("deterministic output: PASS")

assert not hasattr(first, "hidden_reasoning")
assert not hasattr(first, "chain_of_thought")
print("no hidden reasoning fields: PASS")

print("SHY Phase 1 intelligence router tests: PASS")
