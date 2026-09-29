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


providers_path = Path(__file__).resolve().parent
app_path = providers_path.parent
contracts_module = _load_module("shy_model_contracts", app_path / "contracts.py")
base_module = _load_module("shy_model_provider_base", providers_path / "base.py")

ModelCapability = contracts_module.ModelCapability
ModelProfile = contracts_module.ModelProfile
ModelResponse = contracts_module.ModelResponse
ModelUsage = contracts_module.ModelUsage
ProviderHealth = contracts_module.ProviderHealth
ProviderHealthStatus = contracts_module.ProviderHealthStatus
PrivacyClass = contracts_module.PrivacyClass
CostClass = contracts_module.CostClass
LatencyClass = contracts_module.LatencyClass
QualityClass = contracts_module.QualityClass
ModelProvider = base_module.ModelProvider


@dataclass
class OllamaLocalProvider(ModelProvider):
    _model_id: str = "qwen3.5:4b"

    @property
    def provider_id(self) -> str:
        return "ollama"

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderHealthStatus.HEALTHY,
            detail="Local Ollama adapter available.",
        )

    def list_models(self) -> tuple[ModelProfile, ...]:
        return (
            ModelProfile(
                model_id=self._model_id,
                provider_id=self.provider_id,
                display_name="Qwen 3.5 4B (Local)",
                capabilities=(
                    ModelCapability.CHAT,
                    ModelCapability.REASONING,
                    ModelCapability.RESEARCH_SYNTHESIS,
                    ModelCapability.CODING,
                    ModelCapability.TOOL_USE,
                ),
                context_window=8192,
                supports_tools=False,
                supports_vision=False,
                supports_structured_output=False,
                local=True,
                privacy_class=PrivacyClass.LOCAL_ONLY,
                cost_class=CostClass.LOCAL,
                latency_class=LatencyClass.FAST,
                quality_class=QualityClass.STANDARD,
                enabled=True,
            ),
        )

    def generate(self, request: ModelRequest, model_id: str) -> ModelResponse:
        if model_id != self._model_id:
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                error_code="MODEL_NOT_FOUND",
                finish_reason="error",
                metadata={"safe_error": "Requested local model is unavailable."},
            )

        forced_error = request.metadata.get("force_provider_error")
        if forced_error in (self.provider_id, "*"):
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                error_code="PROVIDER_ERROR",
                finish_reason="error",
                metadata={"safe_error": "Provider execution error."},
            )

        forced_invalid = request.metadata.get("force_invalid_response")
        if forced_invalid in (self.provider_id, "*"):
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="OK",
                content="   ",
                finish_reason="stop",
                usage=ModelUsage(input_tokens=None, output_tokens=None),
                latency_ms=5,
                metadata={"adapter": "ollama-local"},
            )

        # Deterministic local adapter response for architecture-layer tests.
        user_messages = [m.content for m in request.messages if m.role == "user"]
        prompt = user_messages[-1] if user_messages else ""

        return ModelResponse(
            provider_id=self.provider_id,
            model_id=model_id,
            status="OK",
            content=f"LOCAL_RESPONSE: {prompt.strip()}",
            finish_reason="stop",
            usage=ModelUsage(input_tokens=None, output_tokens=None),
            latency_ms=5,
            metadata={"adapter": "ollama-local"},
        )
