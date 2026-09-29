import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


def _load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


app_path = Path(__file__).resolve().parent
services_path = app_path.parents[1]

contracts_module = _load_module("shy_model_contracts", app_path / "contracts.py")
registry_module = _load_module("shy_model_registry", app_path / "registry.py")
selection_module = _load_module("shy_model_selection", app_path / "selection.py")
orchestrator_module = _load_module("shy_model_orchestrator", app_path / "orchestrator.py")
ollama_module = _load_module("shy_provider_ollama", app_path / "providers" / "ollama.py")
fake_module = _load_module("shy_provider_fake", app_path / "providers" / "fake.py")
intelligence_router_module = _load_module(
    "shy_intelligence_router_for_model_selection",
    services_path / "agent-runtime" / "intelligence_router.py",
)

ModelCapability = contracts_module.ModelCapability
ModelMessage = contracts_module.ModelMessage
ModelRequest = contracts_module.ModelRequest
PrivacyClass = contracts_module.PrivacyClass
LatencyClass = contracts_module.LatencyClass
CostClass = contracts_module.CostClass
VerificationEscalationAction = contracts_module.VerificationEscalationAction
ModelFailureCategory = contracts_module.ModelFailureCategory
ModelSelectionDecision = contracts_module.ModelSelectionDecision
ModelRegistry = registry_module.ModelRegistry
ModelSelectionInput = selection_module.ModelSelectionInput
ModelSelectionPolicy = selection_module.ModelSelectionPolicy
ModelSelectionPolicyConfig = selection_module.ModelSelectionPolicyConfig
TaskComplexity = selection_module.TaskComplexity
ModelOrchestrator = orchestrator_module.ModelOrchestrator
OrchestratorLimits = orchestrator_module.OrchestratorLimits
OllamaLocalProvider = ollama_module.OllamaLocalProvider
build_default_fake_providers = fake_module.build_default_fake_providers
IntelligenceRouter = intelligence_router_module.IntelligenceRouter


TaskType = Literal[
    "general",
    "reasoning",
    "deep_reasoning",
    "coding",
    "vision",
    "research",
]


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    task_type: TaskType
    reason: str


def map_intelligence_to_capability(intelligence_decision) -> ModelCapability:
    primary = str(getattr(intelligence_decision.primary_capability, "value", "CHAT"))
    complexity = str(getattr(intelligence_decision.complexity, "value", "SIMPLE"))

    if primary == "CODING":
        return ModelCapability.CODING
    if primary == "RESEARCH":
        return ModelCapability.RESEARCH_SYNTHESIS
    if primary == "MULTI_STEP" and complexity == "COMPLEX":
        return ModelCapability.DEEP_REASONING
    if primary in ("REASONING", "MULTI_STEP"):
        return ModelCapability.REASONING
    return ModelCapability.CHAT


class ModelRouter:
    """
    SHY model-independent router.

    The local model remains a first-class option, while provider/model
    selection is capability- and policy-driven behind registry/policy contracts.
    """

    def __init__(
        self,
        local_model: str,
        include_fake_providers: bool | None = None,
    ):
        self.local_model = local_model
        self.include_fake_providers = (
            include_fake_providers
            if include_fake_providers is not None
            else os.getenv("SHY_ENABLE_FAKE_PROVIDERS", "0").strip() == "1"
        )

        self.intelligence_router = IntelligenceRouter()
        self.registry = self._build_registry()
        self.selection_policy = ModelSelectionPolicy(
            ModelSelectionPolicyConfig(
                max_attempts=3,
                max_escalations=2,
                allow_capability_degradation=False,
                include_unknown_health=False,
            )
        )
        self.orchestrator = ModelOrchestrator(
            registry=self.registry,
            selection_policy=self.selection_policy,
            limits=OrchestratorLimits(max_attempts=3, max_escalations=2),
        )

    def _build_registry(self) -> ModelRegistry:
        registry = ModelRegistry()

        local_provider = OllamaLocalProvider(_model_id=self.local_model)
        registry.register_provider(local_provider)
        for model in local_provider.list_models():
            registry.register_model(model)

        if self.include_fake_providers:
            for provider in build_default_fake_providers():
                registry.register_provider(provider)
                for model in provider.list_models():
                    registry.register_model(model)

        return registry

    def classify(self, message: str) -> TaskType:
        text = message.lower()

        coding_terms = (
            "code", "python", "javascript", "typescript",
            "react", "debug", "function", "api", "program",
        )

        deep_reasoning_terms = (
            "deep reasoning", "prove", "formal", "multi-stage",
            "five constraints", "long context", "complex strategy",
        )

        vision_terms = (
            "image", "photo", "picture", "screenshot", "vision",
        )

        research_terms = (
            "research", "sources", "latest", "search the web",
            "look up", "find online",
        )

        reasoning_terms = (
            "analyze", "reason", "compare", "strategy",
            "plan", "solve", "explain why",
        )

        if any(term in text for term in coding_terms):
            return "coding"

        if any(term in text for term in deep_reasoning_terms):
            return "deep_reasoning"

        if any(term in text for term in vision_terms):
            return "vision"

        if any(term in text for term in research_terms):
            return "research"

        if any(term in text for term in reasoning_terms):
            return "reasoning"

        return "general"

    def select_model_for_message(
        self,
        message: str,
        privacy_requirement: PrivacyClass | None = None,
        escalation_level: int = 0,
        metadata: dict | None = None,
    ):
        intelligence_decision = self.intelligence_router.analyze(message)
        required_capability = map_intelligence_to_capability(intelligence_decision)

        complexity = TaskComplexity.SIMPLE
        complexity_name = str(getattr(intelligence_decision.complexity, "value", "SIMPLE"))

        if complexity_name == "COMPLEX":
            complexity = TaskComplexity.COMPLEX
        elif complexity_name == "MODERATE":
            complexity = TaskComplexity.MODERATE

        if required_capability == ModelCapability.CODING:
            cost_preference = CostClass.MEDIUM
            latency_preference = LatencyClass.NORMAL
        elif required_capability == ModelCapability.DEEP_REASONING:
            cost_preference = CostClass.HIGH
            latency_preference = LatencyClass.SLOW
        else:
            cost_preference = CostClass.LOCAL
            latency_preference = LatencyClass.FAST

        selection_input = ModelSelectionInput(
            required_capability=required_capability,
            complexity=complexity,
            requires_external_evidence=bool(getattr(intelligence_decision, "requires_external_evidence", False)),
            coding_required=(required_capability == ModelCapability.CODING),
            privacy_requirement=privacy_requirement or self._privacy_requirement(message),
            latency_preference=latency_preference,
            cost_preference=cost_preference,
            verification_required=bool(getattr(intelligence_decision, "verification_required", False)),
            escalation_level=escalation_level,
        )

        request = ModelRequest(
            messages=(ModelMessage(role="user", content=message),),
            capability=required_capability,
            metadata=dict(metadata or {}),
        )

        return self.orchestrator.run(request=request, selection_input=selection_input)

    def route(self, message: str) -> ModelRoute:
        task_type = self.classify(message)
        result = self.select_model_for_message(message)

        if result.decision is not None:
            reason = result.decision.selection_reason_code.value
            provider_label = result.decision.selected_provider_id
            if provider_label == "ollama":
                provider_label = "ollama-local"
            return ModelRoute(
                provider=provider_label,
                model=result.decision.selected_model_id,
                task_type=task_type,
                reason=reason,
            )

        # Fail closed with deterministic local compatibility fallback.
        return ModelRoute(
            provider="ollama",
            model=self.local_model,
            task_type=task_type,
            reason=ModelFailureCategory.NO_CAPABLE_MODEL.value,
        )

    @staticmethod
    def _privacy_requirement(message: str) -> PrivacyClass:
        text = message.lower()
        if any(term in text for term in ("offline", "local only", "do not send remotely", "private local")):
            return PrivacyClass.LOCAL_ONLY
        if any(term in text for term in ("private", "sensitive", "confidential")):
            return PrivacyClass.PRIVATE_REMOTE_ALLOWED
        return PrivacyClass.REMOTE_ALLOWED


def map_verification_escalation(action: VerificationEscalationAction) -> int | None:
    if action == VerificationEscalationAction.ESCALATE_MODEL:
        return 1
    if action in (
        VerificationEscalationAction.RETRY_SAME_MODEL,
        VerificationEscalationAction.TRY_FALLBACK,
    ):
        return 0
    return None
