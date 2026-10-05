import importlib.util
import os
import sys
from dataclasses import dataclass
from enum import Enum
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
intelligence_candidates = (
    services_path / "agent-runtime" / "intelligence_router.py",
    services_path / "agent_runtime" / "intelligence_router.py",
    app_path.parent / "agent-runtime" / "intelligence_router.py",
    app_path.parent / "agent_runtime" / "intelligence_router.py",
    Path("/app") / "agent-runtime" / "intelligence_router.py",
    Path("/app") / "agent_runtime" / "intelligence_router.py",
)
intelligence_router_module = None
for intelligence_path in intelligence_candidates:
    if intelligence_path.exists():
        intelligence_router_module = _load_module(
            "shy_intelligence_router_for_model_selection",
            intelligence_path,
        )
        break
if intelligence_router_module is None:
    raise FileNotFoundError("Unable to locate intelligence_router.py in the runtime layout")

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
ModelSelectionInput = selection_module.ModelSelectionInput
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


class ModelRole(str, Enum):
    FAST = "FAST"
    GENERAL = "GENERAL"
    REASONING = "REASONING"
    CODING = "CODING"
    RESEARCH = "RESEARCH"
    VERIFIER = "VERIFIER"
    PLANNER = "PLANNER"


class RoutingReasonCode(str, Enum):
    FAST_GENERAL = "FAST_GENERAL"
    COMPLEX_REASONING = "COMPLEX_REASONING"
    CODE_TASK = "CODE_TASK"
    RESEARCH_SYNTHESIS = "RESEARCH_SYNTHESIS"
    VERIFICATION = "VERIFICATION"
    PLANNING = "PLANNING"
    FALLBACK_PROVIDER = "FALLBACK_PROVIDER"
    LOCAL_PRIVACY = "LOCAL_PRIVACY"


@dataclass(frozen=True)
class ModelRoutingCandidate:
    provider_id: str
    model_id: str
    provider_health: str
    latency_tier: str
    cost_tier: str


@dataclass(frozen=True)
class ModelRoutingDecision:
    task_type: TaskType
    role: ModelRole
    required_capability: ModelCapability
    selected_provider: str
    selected_model: str
    reason_code: RoutingReasonCode
    fallback_candidates: tuple[ModelRoutingCandidate, ...]
    provider_health: str
    latency_tier: str
    cost_tier: str


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


def map_intelligence_to_task_type(intelligence_decision) -> TaskType:
    primary = str(getattr(intelligence_decision.primary_capability, "value", "CHAT"))
    complexity = str(getattr(intelligence_decision.complexity, "value", "SIMPLE"))

    if primary == "CODING":
        return "coding"
    if primary == "RESEARCH":
        return "research"
    if primary == "MULTI_STEP" and complexity == "COMPLEX":
        return "deep_reasoning"
    if primary in ("REASONING", "MULTI_STEP"):
        return "reasoning"
    return "general"


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

    @staticmethod
    def role_for_task(
        task_type: TaskType,
        response_mode: str | None = None,
        verification_required: bool = False,
    ) -> ModelRole:
        if response_mode == "research":
            return ModelRole.RESEARCH
        if verification_required or response_mode == "verify":
            return ModelRole.VERIFIER
        if task_type == "coding":
            return ModelRole.CODING
        if task_type in ("reasoning", "deep_reasoning"):
            return ModelRole.REASONING
        if task_type == "research":
            return ModelRole.RESEARCH
        return ModelRole.FAST

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

    def classify(self, message: str, intelligence_decision=None) -> TaskType:
        decision = intelligence_decision or self.intelligence_router.analyze(message)
        task_type = map_intelligence_to_task_type(decision)

        if task_type != "general":
            return task_type

        text = message.lower()
        if any(term in text for term in ("image", "photo", "picture", "screenshot", "vision")):
            return "vision"

        return "general"

    @staticmethod
    def _capability_for_role(role: ModelRole, intelligence_decision) -> ModelCapability:
        if role == ModelRole.CODING:
            return ModelCapability.CODING
        if role == ModelRole.RESEARCH:
            return ModelCapability.RESEARCH_SYNTHESIS
        if role == ModelRole.VERIFIER:
            return ModelCapability.REASONING
        if role == ModelRole.PLANNER:
            return ModelCapability.REASONING
        if role == ModelRole.REASONING:
            complexity_name = str(getattr(intelligence_decision.complexity, "value", "SIMPLE"))
            if complexity_name == "COMPLEX":
                return ModelCapability.DEEP_REASONING
            return ModelCapability.REASONING
        return ModelCapability.CHAT

    @staticmethod
    def _reason_code_for_role(
        role: ModelRole,
        privacy_requirement: PrivacyClass,
        used_fallback: bool,
    ) -> RoutingReasonCode:
        if privacy_requirement == PrivacyClass.LOCAL_ONLY:
            return RoutingReasonCode.LOCAL_PRIVACY
        if used_fallback:
            return RoutingReasonCode.FALLBACK_PROVIDER
        if role in (ModelRole.FAST, ModelRole.GENERAL):
            return RoutingReasonCode.FAST_GENERAL
        if role == ModelRole.REASONING:
            return RoutingReasonCode.COMPLEX_REASONING
        if role == ModelRole.CODING:
            return RoutingReasonCode.CODE_TASK
        if role == ModelRole.RESEARCH:
            return RoutingReasonCode.RESEARCH_SYNTHESIS
        if role == ModelRole.VERIFIER:
            return RoutingReasonCode.VERIFICATION
        return RoutingReasonCode.PLANNING

    def _build_selection_input(
        self,
        message: str,
        required_capability: ModelCapability,
        privacy_requirement: PrivacyClass,
        escalation_level: int,
        intelligence_decision,
    ) -> ModelSelectionInput:
        complexity = TaskComplexity.SIMPLE
        complexity_name = str(getattr(intelligence_decision.complexity, "value", "SIMPLE"))

        if complexity_name == "COMPLEX":
            complexity = TaskComplexity.COMPLEX
        elif complexity_name == "MODERATE":
            complexity = TaskComplexity.MODERATE

        if required_capability == ModelCapability.CODING:
            if complexity == TaskComplexity.COMPLEX:
                cost_preference = CostClass.HIGH
                latency_preference = LatencyClass.SLOW
            else:
                cost_preference = CostClass.MEDIUM
                latency_preference = LatencyClass.NORMAL
        elif required_capability == ModelCapability.DEEP_REASONING:
            cost_preference = CostClass.HIGH
            latency_preference = LatencyClass.SLOW
        elif required_capability == ModelCapability.RESEARCH_SYNTHESIS:
            cost_preference = CostClass.MEDIUM
            latency_preference = LatencyClass.NORMAL
        else:
            cost_preference = CostClass.LOCAL
            latency_preference = LatencyClass.FAST

        _ = message
        return ModelSelectionInput(
            required_capability=required_capability,
            complexity=complexity,
            requires_external_evidence=bool(getattr(intelligence_decision, "requires_external_evidence", False)),
            coding_required=(required_capability == ModelCapability.CODING),
            privacy_requirement=privacy_requirement,
            latency_preference=latency_preference,
            cost_preference=cost_preference,
            verification_required=bool(getattr(intelligence_decision, "verification_required", False)),
            escalation_level=escalation_level,
        )

    def build_routing_decision(
        self,
        message: str,
        role: ModelRole,
        privacy_requirement: PrivacyClass | None = None,
        escalation_level: int = 0,
        metadata: dict | None = None,
        intelligence_decision=None,
        task_type: TaskType | None = None,
    ) -> ModelRoutingDecision | None:
        intelligence_decision = intelligence_decision or self.intelligence_router.analyze(message)
        task_type = task_type or self.classify(message, intelligence_decision=intelligence_decision)
        privacy_requirement = privacy_requirement or self._privacy_requirement(message)
        required_capability = self._capability_for_role(role, intelligence_decision)
        selection_input = self._build_selection_input(
            message=message,
            required_capability=required_capability,
            privacy_requirement=privacy_requirement,
            escalation_level=escalation_level,
            intelligence_decision=intelligence_decision,
        )

        retry_models = tuple((metadata or {}).get("retry_model_ids", ()))
        excluded = set(str(item) for item in retry_models)
        candidates: list[ModelRoutingCandidate] = []

        while len(candidates) < 3:
            decision = self.selection_policy.select(
                registry=self.registry,
                selection_input=selection_input,
                exclude_model_ids=excluded,
            )
            if decision is None:
                break

            profile = self.registry.get_model(decision.selected_model_id)
            health = self.registry.provider_health(decision.selected_provider_id)
            candidate = ModelRoutingCandidate(
                provider_id=decision.selected_provider_id,
                model_id=decision.selected_model_id,
                provider_health=health.status.value,
                latency_tier=profile.latency_class.value,
                cost_tier=profile.cost_class.value,
            )
            candidates.append(candidate)
            excluded.add(decision.selected_model_id)

        if not candidates:
            return None

        primary = candidates[0]
        reason_code = self._reason_code_for_role(role, privacy_requirement, used_fallback=False)
        return ModelRoutingDecision(
            task_type=task_type,
            role=role,
            required_capability=required_capability,
            selected_provider=primary.provider_id,
            selected_model=primary.model_id,
            reason_code=reason_code,
            fallback_candidates=tuple(candidates[1:3]),
            provider_health=primary.provider_health,
            latency_tier=primary.latency_tier,
            cost_tier=primary.cost_tier,
        )

    def select_model_for_message(
        self,
        message: str,
        privacy_requirement: PrivacyClass | None = None,
        escalation_level: int = 0,
        metadata: dict | None = None,
        intelligence_decision=None,
    ):
        intelligence_decision = intelligence_decision or self.intelligence_router.analyze(message)
        required_capability = map_intelligence_to_capability(intelligence_decision)

        selection_input = self._build_selection_input(
            message=message,
            required_capability=required_capability,
            privacy_requirement=privacy_requirement or self._privacy_requirement(message),
            escalation_level=escalation_level,
            intelligence_decision=intelligence_decision,
        )

        request = ModelRequest(
            messages=(ModelMessage(role="user", content=message),),
            capability=required_capability,
            metadata={
                **dict(metadata or {}),
                "repository_context_required": bool(
                    getattr(intelligence_decision, "repository_context_required", False)
                ),
                "coding_verification_required": bool(
                    getattr(intelligence_decision, "verification_required", False)
                ),
            },
        )

        return self.orchestrator.run(request=request, selection_input=selection_input)

    def route(
        self,
        message: str,
        privacy_requirement: PrivacyClass | None = None,
        escalation_level: int = 0,
        metadata: dict | None = None,
    ) -> ModelRoute:
        intelligence_decision = self.intelligence_router.analyze(message)
        task_type = self.classify(message, intelligence_decision=intelligence_decision)
        role = self.role_for_task(task_type)
        routing_decision = self.build_routing_decision(
            message,
            role=role,
            privacy_requirement=privacy_requirement,
            escalation_level=escalation_level,
            metadata=metadata,
            intelligence_decision=intelligence_decision,
            task_type=task_type,
        )

        if routing_decision is not None:
            provider_label = routing_decision.selected_provider
            if provider_label == "ollama":
                provider_label = "ollama-local"
            return ModelRoute(
                provider=provider_label,
                model=routing_decision.selected_model,
                task_type=task_type,
                reason=routing_decision.reason_code.value,
            )

        result = self.select_model_for_message(
            message,
            privacy_requirement=privacy_requirement,
            escalation_level=escalation_level,
            metadata=metadata,
            intelligence_decision=intelligence_decision,
        )

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
