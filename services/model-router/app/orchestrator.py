from dataclasses import dataclass
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
selection_module = _load_module("shy_model_selection", app_path / "selection.py")

ModelFailureCategory = contracts_module.ModelFailureCategory
OrchestrationFailure = contracts_module.OrchestrationFailure
OrchestrationResult = contracts_module.OrchestrationResult
SelectionReasonCode = contracts_module.SelectionReasonCode
ModelSelectionInput = selection_module.ModelSelectionInput


@dataclass(frozen=True)
class OrchestratorLimits:
    max_attempts: int = 3
    max_escalations: int = 2


class ModelOrchestrator:
    def __init__(
        self,
        registry,
        selection_policy,
        limits: OrchestratorLimits | None = None,
    ):
        self.registry = registry
        self.selection_policy = selection_policy
        self.limits = limits or OrchestratorLimits()

    def run(
        self,
        request,
        selection_input: ModelSelectionInput,
    ) -> OrchestrationResult:
        attempted: set[str] = set()
        attempts_used = 0
        escalations_used = selection_input.escalation_level

        if selection_input.escalation_level > self.limits.max_escalations:
            return OrchestrationResult(
                decision=None,
                response=None,
                attempts_used=0,
                escalations_used=self.limits.max_escalations,
                failure=OrchestrationFailure(
                    category=ModelFailureCategory.ESCALATION_LIMIT_REACHED,
                    reason_code=SelectionReasonCode.VERIFICATION_ESCALATION.value,
                    safe_message="Escalation limit reached.",
                ),
            )

        while attempts_used < self.limits.max_attempts:
            decision = self.selection_policy.select(
                registry=self.registry,
                selection_input=selection_input,
                exclude_model_ids=attempted,
            )

            if decision is None:
                reason = (
                    SelectionReasonCode.PRIVACY_POLICY_BLOCKED
                    if selection_input.required_capability is not None
                    else SelectionReasonCode.NO_CAPABLE_MODEL
                )
                return OrchestrationResult(
                    decision=None,
                    response=None,
                    attempts_used=attempts_used,
                    escalations_used=escalations_used,
                    failure=OrchestrationFailure(
                        category=ModelFailureCategory.NO_CAPABLE_MODEL,
                        reason_code=reason.value,
                        safe_message="No compatible model is available for this request.",
                    ),
                )

            attempted.add(decision.selected_model_id)
            attempts_used += 1

            provider = self.registry.get_provider(decision.selected_provider_id)

            try:
                response = provider.generate(request=request, model_id=decision.selected_model_id)
            except Exception:
                if attempts_used >= self.limits.max_attempts:
                    return OrchestrationResult(
                        decision=decision,
                        response=None,
                        attempts_used=attempts_used,
                        escalations_used=escalations_used,
                        failure=OrchestrationFailure(
                            category=ModelFailureCategory.ATTEMPT_LIMIT_REACHED,
                            reason_code=SelectionReasonCode.ATTEMPT_LIMIT_REACHED.value,
                            safe_message="Model attempt limit reached.",
                        ),
                    )
                continue

            failure = self._response_failure(response)
            if failure is None:
                return OrchestrationResult(
                    decision=decision,
                    response=response,
                    attempts_used=attempts_used,
                    escalations_used=escalations_used,
                    failure=None,
                )

            if attempts_used >= self.limits.max_attempts:
                return OrchestrationResult(
                    decision=decision,
                    response=response,
                    attempts_used=attempts_used,
                    escalations_used=escalations_used,
                    failure=OrchestrationFailure(
                        category=ModelFailureCategory.ATTEMPT_LIMIT_REACHED,
                        reason_code=SelectionReasonCode.ATTEMPT_LIMIT_REACHED.value,
                        safe_message="Model attempt limit reached.",
                    ),
                )

        return OrchestrationResult(
            decision=None,
            response=None,
            attempts_used=attempts_used,
            escalations_used=escalations_used,
            failure=OrchestrationFailure(
                category=ModelFailureCategory.ATTEMPT_LIMIT_REACHED,
                reason_code=SelectionReasonCode.ATTEMPT_LIMIT_REACHED.value,
                safe_message="Model attempt limit reached.",
            ),
        )

    @staticmethod
    def _response_failure(response) -> ModelFailureCategory | None:
        if response.status != "OK":
            if response.error_code == "PROVIDER_UNAVAILABLE":
                return ModelFailureCategory.PROVIDER_UNAVAILABLE
            if response.error_code == "TIMEOUT":
                return ModelFailureCategory.TIMEOUT
            if response.error_code:
                return ModelFailureCategory.PROVIDER_ERROR
            return ModelFailureCategory.MODEL_ERROR

        if not response.content.strip():
            return ModelFailureCategory.INVALID_RESPONSE

        return None
