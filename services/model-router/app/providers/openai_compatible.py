from dataclasses import dataclass
import importlib.util
import sys
import time
from pathlib import Path

import httpx


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

CostClass = contracts_module.CostClass
LatencyClass = contracts_module.LatencyClass
ModelCapability = contracts_module.ModelCapability
ModelProfile = contracts_module.ModelProfile
ModelResponse = contracts_module.ModelResponse
ModelUsage = contracts_module.ModelUsage
PrivacyClass = contracts_module.PrivacyClass
ProviderHealth = contracts_module.ProviderHealth
ProviderHealthStatus = contracts_module.ProviderHealthStatus
QualityClass = contracts_module.QualityClass
ModelProvider = base_module.ModelProvider


@dataclass
class OpenAICompatibleRemoteProvider(ModelProvider):
    _model_id: str
    _base_url: str
    _api_key: str = ""
    _provider_id: str = "qwen_remote"

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def _configured(self) -> bool:
        return bool(self._model_id.strip() and self._base_url.strip())

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self._api_key.strip():
            headers["authorization"] = f"Bearer {self._api_key.strip()}"
        return headers

    def health(self) -> ProviderHealth:
        status = ProviderHealthStatus.HEALTHY if self._configured() else ProviderHealthStatus.UNAVAILABLE
        return ProviderHealth(
            provider_id=self.provider_id,
            status=status,
            detail="Configured OpenAI-compatible private remote inference provider.",
        )

    def probe(self) -> bool:
        if not self._configured():
            return False
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(
                    f"{self._base_url.rstrip('/')}/models",
                    headers=self._headers(),
                )
            return response.is_success
        except httpx.HTTPError:
            return False

    def list_models(self) -> tuple[ModelProfile, ...]:
        return (
            ModelProfile(
                model_id=self._model_id,
                provider_id=self.provider_id,
                display_name="Qwen 3.5 4B (Private Remote)",
                capabilities=(
                    ModelCapability.CHAT,
                    ModelCapability.REASONING,
                    ModelCapability.DEEP_REASONING,
                    ModelCapability.RESEARCH_SYNTHESIS,
                    ModelCapability.CODING,
                    ModelCapability.VISION,
                    ModelCapability.LONG_CONTEXT,
                ),
                context_window=32768,
                supports_tools=False,
                supports_vision=True,
                supports_structured_output=False,
                local=False,
                privacy_class=PrivacyClass.PRIVATE_REMOTE_ALLOWED,
                cost_class=CostClass.MEDIUM,
                latency_class=LatencyClass.NORMAL,
                quality_class=QualityClass.HIGH,
                enabled=self._configured(),
            ),
        )

    def generate(self, request, model_id: str) -> ModelResponse:
        if model_id != self._model_id:
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                error_code="MODEL_NOT_FOUND",
                finish_reason="error",
                metadata={"safe_error": "Requested remote model is unavailable."},
            )

        if not self._configured():
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                error_code="PROVIDER_UNAVAILABLE",
                finish_reason="error",
                metadata={"safe_error": "Remote model provider is not configured."},
            )

        payload = {
            "model": model_id,
            "messages": [
                {"role": str(message.role), "content": str(message.content)}
                for message in request.messages
            ],
            "stream": False,
        }
        if request.temperature is not None:
            payload["temperature"] = float(request.temperature)
        if request.max_output_tokens is not None:
            payload["max_tokens"] = int(request.max_output_tokens)

        started = time.monotonic()
        try:
            with httpx.Client(timeout=180.0) as client:
                response = client.post(
                    f"{self._base_url.rstrip('/')}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
        except httpx.TimeoutException:
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                error_code="TIMEOUT",
                finish_reason="error",
                metadata={"safe_error": "Remote model timed out."},
            )
        except (httpx.HTTPError, ValueError, TypeError):
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                error_code="PROVIDER_ERROR",
                finish_reason="error",
                metadata={"safe_error": "Remote model provider returned an error."},
            )

        choices = result.get("choices") if isinstance(result, dict) else None
        first_choice = choices[0] if isinstance(choices, list) and choices else None
        message = first_choice.get("message") if isinstance(first_choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="OK",
                content="",
                finish_reason="stop",
                latency_ms=int((time.monotonic() - started) * 1000),
                metadata={"adapter": "openai-compatible-remote"},
            )

        usage = result.get("usage") if isinstance(result, dict) else None
        input_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        output_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
        finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None

        return ModelResponse(
            provider_id=self.provider_id,
            model_id=model_id,
            status="OK",
            content=content.strip(),
            finish_reason=str(finish_reason) if finish_reason is not None else "stop",
            usage=ModelUsage(
                input_tokens=int(input_tokens) if isinstance(input_tokens, int) else None,
                output_tokens=int(output_tokens) if isinstance(output_tokens, int) else None,
            ),
            latency_ms=int((time.monotonic() - started) * 1000),
            metadata={"adapter": "openai-compatible-remote"},
        )
