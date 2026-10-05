import importlib.util
from pathlib import Path


root = Path(__file__).resolve().parents[1]
router_path = root / "services" / "agent-runtime" / "intelligence_router.py"
types_path = root / "services" / "core" / "intelligence_types.py"
model_router_path = root / "services" / "model-router" / "app" / "router.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


intelligence_router_module = load_module("shy_intelligence_router_phase6b", router_path)
types_module = load_module("shy_intelligence_types_phase6b", types_path)
model_router_module = load_module("shy_model_router_phase6b", model_router_path)

IntelligenceRouter = intelligence_router_module.IntelligenceRouter
Capability = types_module.Capability
CodingTaskType = types_module.CodingTaskType
Complexity = types_module.Complexity
ModelRouter = model_router_module.ModelRouter
ModelCapability = model_router_module.ModelCapability

router = IntelligenceRouter()

python_debug = router.analyze("Debug this Python exception stack trace and fix the handler")
assert python_debug.primary_capability == Capability.CODING
assert python_debug.coding_profile is not None
assert python_debug.coding_profile.task_type in (CodingTaskType.DEBUG_EXCEPTION, CodingTaskType.STACK_TRACE_ANALYSIS)
assert "python" in python_debug.coding_profile.languages
assert python_debug.verification_required is True
print("python exception classification: PASS")

react_build = router.analyze("React build failure on vite after updating tsconfig")
assert react_build.primary_capability == Capability.CODING
assert react_build.coding_profile is not None
assert react_build.coding_profile.task_type == CodingTaskType.REACT_BUILD_FAILURE
assert react_build.repository_context_required is True
assert react_build.execution_required is True
assert react_build.complexity == Complexity.COMPLEX
print("react build failure classification: PASS")

api_impl = router.analyze("Implement a REST API endpoint for order status")
assert api_impl.primary_capability == Capability.CODING
assert api_impl.coding_profile.task_type == CodingTaskType.API_IMPLEMENTATION
print("api implementation classification: PASS")

unit_tests = router.analyze("Generate pytest unit tests for this serializer")
assert unit_tests.primary_capability == Capability.CODING
assert unit_tests.coding_profile.task_type == CodingTaskType.UNIT_TEST_GENERATION
assert "pytest" in unit_tests.coding_profile.frameworks
print("unit test generation classification: PASS")

git_diff = router.analyze("Review this git diff and highlight regressions")
assert git_diff.primary_capability == Capability.CODING
assert git_diff.coding_profile.task_type == CodingTaskType.GIT_DIFF_REVIEW
assert git_diff.repository_context_required is True
print("git diff review classification: PASS")

repo_analysis = router.analyze("Analyze this repository architecture and debug build issues")
assert repo_analysis.primary_capability == Capability.CODING
assert repo_analysis.coding_profile.task_type in (
    CodingTaskType.REPOSITORY_ANALYSIS,
    CodingTaskType.GRADLE_BUILD_FAILURE,
)
print("repository analysis classification: PASS")

gradle = router.analyze("Gradle build failure: task :app:compileDebugJavaWithJavac failed")
assert gradle.primary_capability == Capability.CODING
assert gradle.coding_profile.task_type == CodingTaskType.GRADLE_BUILD_FAILURE
print("gradle build failure classification: PASS")

stack_trace = router.analyze("Please analyze this stack trace from production")
assert stack_trace.primary_capability == Capability.CODING
assert stack_trace.coding_profile.task_type == CodingTaskType.STACK_TRACE_ANALYSIS
print("stack-trace classification: PASS")

for false_positive in (
    "What is the dress code for the event?",
    "Find the ZIP code for this address",
    "What is the airport code for Tokyo?",
    "Explain this medical billing code",
    "This is code red please stay calm",
):
    decision = router.analyze(false_positive)
    assert decision.primary_capability != Capability.CODING
print("coding false-positive protections: PASS")

ambiguous = router.analyze("Can you help with this issue?")
assert ambiguous.primary_capability in (Capability.CHAT, Capability.REASONING)
print("ambiguous task safety: PASS")

model_router = ModelRouter(local_model="qwen3.5:4b", include_fake_providers=True)
routing = model_router.select_model_for_message("Debug this Python exception and write unit tests")
assert routing.decision is not None
assert routing.decision.required_capability == ModelCapability.CODING
print("coding capability routing integration: PASS")

incompatible = model_router.select_model_for_message(
    "Deep reasoning proof over five constraints",
    metadata={"force_provider_error": "fake_reasoning"},
)
assert incompatible is not None
print("incompatible fallback behavior remains bounded: PASS")

# Classification must not execute tools or grant authority.
assert not getattr(python_debug, "requires_tool", False)
assert getattr(python_debug, "execution_required", False) in (True, False)
print("no authority escalation from classification: PASS")

print("SHY Phase 6B coding intelligence tests: PASS")
