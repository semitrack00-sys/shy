import importlib.util
import os
import sys
from pathlib import Path


root = Path(__file__).resolve().parents[1]
router_path = root / "services" / "model-router" / "app" / "router.py"
contracts_path = root / "services" / "model-router" / "app" / "contracts.py"
registry_path = root / "services" / "model-router" / "app" / "registry.py"
selection_path = root / "services" / "model-router" / "app" / "selection.py"
orchestrator_path = root / "services" / "model-router" / "app" / "orchestrator.py"
fake_path = root / "services" / "model-router" / "app" / "providers" / "fake.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contracts = load_module("shy_model_contracts", contracts_path)
registry_module = load_module("shy_model_registry", registry_path)
selection_module = load_module("shy_model_selection", selection_path)
orchestrator_module = load_module("shy_model_orchestrator", orchestrator_path)
fake_module = load_module("shy_provider_fake", fake_path)
router_module = load_module("shy_model_router_test", router_path)


ModelCapability = contracts.ModelCapability
PrivacyClass = contracts.PrivacyClass
CostClass = contracts.CostClass
LatencyClass = contracts.LatencyClass
QualityClass = contracts.QualityClass
ProviderHealthStatus = contracts.ProviderHealthStatus
ModelFailureCategory = contracts.ModelFailureCategory
VerificationEscalationAction = contracts.VerificationEscalationAction
ModelMessage = contracts.ModelMessage
ModelRequest = contracts.ModelRequest
ModelProfile = contracts.ModelProfile

ModelRegistry = registry_module.ModelRegistry
ModelSelectionInput = selection_module.ModelSelectionInput
TaskComplexity = selection_module.TaskComplexity
ModelSelectionPolicy = selection_module.ModelSelectionPolicy
ModelSelectionPolicyConfig = selection_module.ModelSelectionPolicyConfig

ModelOrchestrator = orchestrator_module.ModelOrchestrator
OrchestratorLimits = orchestrator_module.OrchestratorLimits

ModelRouter = router_module.ModelRouter
map_intelligence_to_capability = router_module.map_intelligence_to_capability
map_verification_escalation = router_module.map_verification_escalation


try:
    ModelProfile(
        model_id="",
        provider_id="x",
        display_name="bad",
        capabilities=(ModelCapability.CHAT,),
        context_window=1,
        supports_tools=False,
        supports_vision=False,
        supports_structured_output=False,
        local=True,
        privacy_class=PrivacyClass.LOCAL_ONLY,
        cost_class=CostClass.LOCAL,
        latency_class=LatencyClass.FAST,
        quality_class=QualityClass.STANDARD,
    )
    raise AssertionError("Invalid profile was not rejected")
except ValueError:
    pass
print("ModelProfile validation: PASS")


router = ModelRouter(local_model="qwen3.5:4b", include_fake_providers=True)
registry = router.registry

snapshot = registry.snapshot()
assert "ollama" in snapshot.provider_ids
assert "qwen3.5:4b" in snapshot.model_ids
print("provider registration: PASS")

try:
    provider = registry.get_provider("ollama")
    registry.register_provider(provider)
    raise AssertionError("Duplicate provider was not rejected")
except ValueError:
    pass
print("duplicate provider rejection: PASS")

local_profile = registry.get_model("qwen3.5:4b")
try:
    registry.register_model(local_profile)
    raise AssertionError("Duplicate model was not rejected")
except ValueError:
    pass
print("duplicate model rejection: PASS")

coding_models = registry.models_for_capability(ModelCapability.CODING)
assert any(model.model_id == "fake_coding:model" for model in coding_models)
print("capability filtering: PASS")

provider_health = registry.list_provider_health()
assert provider_health["ollama"].status == ProviderHealthStatus.HEALTHY
print("provider health: PASS")


policy = ModelSelectionPolicy(
    ModelSelectionPolicyConfig(
        max_attempts=3,
        max_escalations=2,
        allow_capability_degradation=False,
        include_unknown_health=False,
    )
)

selection_input = ModelSelectionInput(
    required_capability=ModelCapability.CODING,
    complexity=TaskComplexity.MODERATE,
    coding_required=True,
    privacy_requirement=PrivacyClass.REMOTE_ALLOWED,
    latency_preference=LatencyClass.NORMAL,
    cost_preference=CostClass.MEDIUM,
)

decision_one = policy.select(registry, selection_input)
decision_two = policy.select(registry, selection_input)
assert decision_one == decision_two
assert decision_one.selected_model_id == "fake_coding:model"
print("selection determinism: PASS")
print("coding capability routing: PASS")


deep_input = ModelSelectionInput(
    required_capability=ModelCapability.DEEP_REASONING,
    complexity=TaskComplexity.COMPLEX,
    privacy_requirement=PrivacyClass.REMOTE_ALLOWED,
)
deep_decision = policy.select(registry, deep_input)
assert deep_decision.selected_model_id == "fake_reasoning:model"
print("deep reasoning routing: PASS")

privacy_input = ModelSelectionInput(
    required_capability=ModelCapability.CHAT,
    complexity=TaskComplexity.SIMPLE,
    privacy_requirement=PrivacyClass.LOCAL_ONLY,
)
privacy_decision = policy.select(registry, privacy_input)
assert privacy_decision is not None
assert privacy_decision.selected_provider_id == "ollama"
print("local privacy enforcement: PASS")


# Force preferred coding provider unavailable and verify compatible fallback behavior.
fake_coding_provider = registry.get_provider("fake_coding")
fake_coding_provider.set_health(ProviderHealthStatus.UNAVAILABLE)

fallback_decision = policy.select(registry, selection_input)
assert fallback_decision is not None
assert fallback_decision.selected_provider_id == "ollama"
print("fallback compatibility (compatible fallback accepted): PASS")

deep_only_provider = registry.get_provider("fake_reasoning")
deep_only_provider.set_health(ProviderHealthStatus.UNAVAILABLE)
deep_incompatible = policy.select(registry, deep_input)
assert deep_incompatible is None
print("fallback compatibility (incompatible fallback rejected): PASS")

deep_only_provider.set_health(ProviderHealthStatus.HEALTHY)

fake_coding_provider.set_health(ProviderHealthStatus.HEALTHY)


request = ModelRequest(
    messages=(ModelMessage(role="user", content="Write unit tests for this endpoint"),),
    capability=ModelCapability.CODING,
    metadata={},
)

orchestrator = ModelOrchestrator(
    registry=registry,
    selection_policy=policy,
    limits=OrchestratorLimits(max_attempts=3, max_escalations=2),
)

result = orchestrator.run(request, selection_input)
assert result.failure is None
assert result.response is not None
assert result.response.content.startswith("FAKE_CODING")
print("bounded orchestration success: PASS")


# Provider error should use bounded fallback and not silently succeed on invalid capability.
request_error = ModelRequest(
    messages=(ModelMessage(role="user", content="Need coding fix"),),
    capability=ModelCapability.CODING,
    metadata={"force_provider_error": "fake_coding"},
)
error_result = orchestrator.run(request_error, selection_input)
assert error_result.failure is None
assert error_result.response is not None
assert error_result.attempts_used >= 2
print("provider failure handling: PASS")


request_invalid = ModelRequest(
    messages=(ModelMessage(role="user", content="Need coding fix"),),
    capability=ModelCapability.CODING,
    metadata={"force_invalid_response": "fake_coding"},
)
invalid_result = orchestrator.run(request_invalid, selection_input)
if invalid_result.failure is not None:
    assert invalid_result.failure.safe_message.strip()
    assert "token" not in invalid_result.failure.safe_message.lower()
else:
    assert invalid_result.response is not None
    assert invalid_result.attempts_used >= 2
print("invalid provider response handling: PASS")
print("structured failure sanitization: PASS")


attempt_limited = ModelOrchestrator(
    registry=registry,
    selection_policy=policy,
    limits=OrchestratorLimits(max_attempts=1, max_escalations=0),
)
attempt_result = attempt_limited.run(request_error, selection_input)
assert attempt_result.failure is not None
assert attempt_result.failure.category == ModelFailureCategory.ATTEMPT_LIMIT_REACHED
print("attempt limits: PASS")


assert map_verification_escalation(VerificationEscalationAction.RETRY_SAME_MODEL) == 0
assert map_verification_escalation(VerificationEscalationAction.TRY_FALLBACK) == 0
assert map_verification_escalation(VerificationEscalationAction.ESCALATE_MODEL) == 1
assert map_verification_escalation(VerificationEscalationAction.STOP) is None
print("verification escalation contract: PASS")


local_only_router = ModelRouter(local_model="qwen3.5:4b", include_fake_providers=False)
local_route = local_only_router.route("Hello SHY")
assert local_route.provider == "ollama-local"
assert local_route.model == "qwen3.5:4b"
print("Ollama adapter compatibility: PASS")


fake_route_one = router.route("Fix this Python function")
fake_route_two = router.route("Fix this Python function")
assert fake_route_one == fake_route_two
print("fake providers deterministic: PASS")


research_route = router.route("Research the latest regulation updates")
assert research_route.task_type == "research"

coding_route = router.route("Debug this API handler")
assert coding_route.task_type == "coding"

reasoning_route = router.route("Compare three migration strategies")
assert reasoning_route.task_type in ("reasoning", "deep_reasoning")
print("router task-type mapping: PASS")


decision = router.intelligence_router.analyze("Compare five constraints and plan a multi-stage rollout")
mapped_capability = map_intelligence_to_capability(decision)
assert mapped_capability in (ModelCapability.REASONING, ModelCapability.DEEP_REASONING)
print("router-to-capability mapping: PASS")


original_tavily = os.environ.pop("TAVILY_API_KEY", None)
_ = ModelRouter(local_model="qwen3.5:4b", include_fake_providers=True)
if original_tavily is not None:
    os.environ["TAVILY_API_KEY"] = original_tavily
print("no API key requirement: PASS")


for route in (local_route, fake_route_one, research_route):
    assert not hasattr(route, "chain_of_thought")
    assert not hasattr(route, "hidden_reasoning")
print("no hidden reasoning persistence: PASS")

print("SHY Phase 6A model routing architecture tests: PASS")
