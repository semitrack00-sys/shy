from dataclasses import dataclass
from enum import Enum
import importlib.util
import sys
from pathlib import Path


def _load_module(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


app_path = Path(__file__).resolve().parent
contracts_module = _load_module("shy_model_contracts", app_path / "contracts.py")

CostClass = contracts_module.CostClass
LatencyClass = contracts_module.LatencyClass
ModelCapability = contracts_module.ModelCapability
ModelSelectionDecision = contracts_module.ModelSelectionDecision
PrivacyClass = contracts_module.PrivacyClass
ProviderHealthStatus = contracts_module.ProviderHealthStatus
QualityClass = contracts_module.QualityClass
SelectionReasonCode = contracts_module.SelectionReasonCode


class TaskComplexity(str, Enum):
    SIMPLE = "SIMPLE"
    MODERATE = "MODERATE"
    COMPLEX = "COMPLEX"


@dataclass(frozen=True)
class ModelSelectionInput:
    required_capability: ModelCapability
    complexity: TaskComplexity = TaskComplexity.SIMPLE
    requires_external_evidence: bool = False
    coding_required: bool = False
    privacy_requirement: PrivacyClass = PrivacyClass.REMOTE_ALLOWED
    latency_preference: LatencyClass | None = None
    cost_preference: CostClass | None = None
    verification_required: bool = False
    escalation_level: int = 0


@dataclass(frozen=True)
class ModelSelectionPolicyConfig:
    max_attempts: int = 3
    max_escalations: int = 2
    allow_capability_degradation: bool = False
    include_unknown_health: bool = False


class ModelSelectionPolicy:
    def __init__(self, config: ModelSelectionPolicyConfig | None = None):
        self.config = config or ModelSelectionPolicyConfig()

    def select(
        self,
        registry,
        selection_input: ModelSelectionInput,
        exclude_model_ids: set[str] | None = None,
    ) -> ModelSelectionDecision | None:
        exclude = exclude_model_ids or set()

        candidates = [
            model
            for model in registry.enabled_models()
            if model.model_id not in exclude
        ]

        candidates = [
            model
            for model in candidates
            if self._privacy_compatible(model, selection_input.privacy_requirement)
        ]

        candidates = [
            model
            for model in candidates
            if self._health_compatible(registry, model, self.config.include_unknown_health)
        ]

        capability_matches = [
            model
            for model in candidates
            if selection_input.required_capability in model.capabilities
        ]

        if not capability_matches and not self.config.allow_capability_degradation:
            return None

        ranked = self._rank_candidates(capability_matches or candidates, selection_input)
        if not ranked:
            return None

        selected = ranked[0]
        fallbacks = tuple(item.model_id for item in ranked[1:])

        reason = self._reason_code(selected, selection_input, has_fallback=bool(fallbacks))

        return ModelSelectionDecision(
            selected_provider_id=selected.provider_id,
            selected_model_id=selected.model_id,
            required_capability=selection_input.required_capability,
            selection_reason_code=reason,
            fallback_candidates=fallbacks,
            escalation_allowed=(selection_input.escalation_level < self.config.max_escalations),
            confidence=self._confidence(selected, selection_input),
        )

    @staticmethod
    def _privacy_compatible(model: ModelProfile, requirement: PrivacyClass) -> bool:
        if requirement == PrivacyClass.LOCAL_ONLY:
            return model.local and model.privacy_class == PrivacyClass.LOCAL_ONLY

        if requirement == PrivacyClass.PRIVATE_REMOTE_ALLOWED:
            return model.privacy_class in (
                PrivacyClass.LOCAL_ONLY,
                PrivacyClass.PRIVATE_REMOTE_ALLOWED,
            )

        return True

    @staticmethod
    def _health_compatible(
        registry,
        model,
        include_unknown_health: bool,
    ) -> bool:
        health = registry.provider_health(model.provider_id).status
        if health == ProviderHealthStatus.UNAVAILABLE:
            return False
        if health == ProviderHealthStatus.UNKNOWN and not include_unknown_health:
            return False
        return True

    def _rank_candidates(
        self,
        candidates: list,
        selection_input: ModelSelectionInput,
    ) -> list:
        def score(model: ModelProfile):
            score_value = 0

            if selection_input.privacy_requirement == PrivacyClass.LOCAL_ONLY and model.local:
                score_value += 100

            if selection_input.coding_required and ModelCapability.CODING in model.capabilities:
                score_value += 60

            if selection_input.required_capability == ModelCapability.DEEP_REASONING:
                if ModelCapability.DEEP_REASONING in model.capabilities:
                    score_value += 70
                if model.quality_class in (QualityClass.HIGH, QualityClass.FRONTIER):
                    score_value += 30

            if selection_input.required_capability == ModelCapability.RESEARCH_SYNTHESIS:
                if ModelCapability.RESEARCH_SYNTHESIS in model.capabilities:
                    score_value += 50

            if selection_input.complexity == TaskComplexity.COMPLEX:
                if model.quality_class == QualityClass.FRONTIER:
                    score_value += 30
                elif model.quality_class == QualityClass.HIGH:
                    score_value += 20

            if selection_input.latency_preference is not None:
                if model.latency_class == selection_input.latency_preference:
                    score_value += 12

            if selection_input.cost_preference is not None:
                if model.cost_class == selection_input.cost_preference:
                    score_value += 10

            if model.local:
                score_value += 5

            # Deterministic tie-breakers via model/provider ids.
            return (
                score_value,
                int(model.local),
                model.quality_class.value,
                model.provider_id,
                model.model_id,
            )

        return sorted(candidates, key=score, reverse=True)

    @staticmethod
    def _reason_code(
        selected,
        selection_input: ModelSelectionInput,
        has_fallback: bool,
    ) -> SelectionReasonCode:
        if selection_input.privacy_requirement == PrivacyClass.LOCAL_ONLY:
            return SelectionReasonCode.PRIVACY_LOCAL_REQUIRED

        if selection_input.escalation_level > 0:
            return SelectionReasonCode.VERIFICATION_ESCALATION

        if selection_input.required_capability == ModelCapability.CODING:
            return SelectionReasonCode.CODING_SPECIALIST_REQUIRED

        if selection_input.required_capability == ModelCapability.DEEP_REASONING:
            return SelectionReasonCode.DEEP_REASONING_REQUIRED

        if selected.local and selection_input.complexity == TaskComplexity.SIMPLE:
            return SelectionReasonCode.LOCAL_SUFFICIENT

        if has_fallback:
            return SelectionReasonCode.CAPABILITY_MATCH

        return SelectionReasonCode.LOCAL_SUFFICIENT if selected.local else SelectionReasonCode.FRONTIER_REQUIRED

    @staticmethod
    def _confidence(selected, selection_input: ModelSelectionInput) -> float:
        confidence = 0.7

        if selection_input.required_capability in selected.capabilities:
            confidence += 0.15

        if selection_input.complexity == TaskComplexity.COMPLEX and selected.quality_class in (
            QualityClass.HIGH,
            QualityClass.FRONTIER,
        ):
            confidence += 0.1

        if selection_input.privacy_requirement == PrivacyClass.LOCAL_ONLY and selected.local:
            confidence += 0.05

        return min(1.0, round(confidence, 2))
