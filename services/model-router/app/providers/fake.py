from dataclasses import dataclass
import hashlib
import importlib.util
import re
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


def _deterministic_content(prefix: str, request) -> str:
    user_messages = [m.content for m in request.messages if m.role == "user"]
    latest = user_messages[-1] if user_messages else ""
    return f"{prefix}: {latest.strip()}"


@dataclass
class DeterministicFakeProvider(ModelProvider):
    _provider_id: str
    _profile: ModelProfile
    _health: ProviderHealthStatus = ProviderHealthStatus.HEALTHY
    _mode: str = "ok"
    _call_count: int = 0
    _success_count: int = 0
    _failure_count: int = 0
    _last_request_summary: dict | None = None

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def set_health(self, status: ProviderHealthStatus):
        if isinstance(status, str):
            self._health = ProviderHealthStatus(status.strip().upper())
            return
        self._health = status

    def set_mode(self, mode: str):
        allowed = {"ok", "error", "empty", "malformed", "timeout", "unavailable"}
        normalized = str(mode or "ok").strip().lower()
        if normalized not in allowed:
            raise ValueError(f"unsupported fake provider mode: {mode}")
        self._mode = normalized

    def reset_stats(self):
        self._call_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._last_request_summary = None

    def stats(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "mode": self._mode,
            "call_count": self._call_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "health": self._health.value,
            "last_request_summary": dict(self._last_request_summary or {}),
        }

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            status=self._health,
            detail="Deterministic fake provider for offline testing.",
        )

    def list_models(self) -> tuple[ModelProfile, ...]:
        return (self._profile,)

    def generate(self, request, model_id: str) -> ModelResponse:
        self._call_count += 1
        all_messages = [str(getattr(m, "content", "")) for m in request.messages]
        non_system_messages = [
            str(getattr(m, "content", ""))
            for m in request.messages
            if str(getattr(m, "role", "")).lower() != "system"
        ]
        user_messages = [m.content for m in request.messages if getattr(m, "role", "") == "user"]
        latest_user = user_messages[-1] if user_messages else ""
        memory_lines = []
        for item in all_messages:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if "Relevant memory context:" in text:
                memory_lines.append(text)
                continue
            if text.startswith("- ["):
                memory_lines.append(text)
        lowered_all = "\n".join(non_system_messages).lower()
        evidence_block = ""
        if "EXTERNAL EVIDENCE:" in str(latest_user):
            evidence_block = str(latest_user).split("EXTERNAL EVIDENCE:", 1)[1].strip()
        normalized_evidence = "\n".join(line.rstrip() for line in evidence_block.splitlines()).strip()
        evidence_fingerprint = ""
        evidence_item_count = 0
        if normalized_evidence:
            evidence_fingerprint = hashlib.sha256(normalized_evidence.encode("utf-8")).hexdigest()
            evidence_item_count = len(re.findall(r"^\[\d+\]\s+TITLE:", normalized_evidence, flags=re.MULTILINE))
        secret_markers = ("password", "api key", "oauth", "approval token", "database_url", "private key")
        secret_marker_hits = [token for token in secret_markers if token in lowered_all]
        contains_secret_marker = bool(secret_marker_hits)
        contains_hidden_reasoning_marker = any(
            token in lowered_all
            for token in ("chain-of-thought", "hidden reasoning", "verifier reasoning", "step_id", "action_type")
        )
        self._last_request_summary = {
            "message_count": len(tuple(request.messages)),
            "has_memory_context": bool(memory_lines),
            "memory_line_count": len(memory_lines),
            "latest_user_length": len(str(latest_user)),
            "contains_secret_marker": contains_secret_marker,
            "secret_marker_hits": secret_marker_hits,
            "contains_hidden_reasoning_marker": contains_hidden_reasoning_marker,
            "contains_superseded_marker": "superseded" in lowered_all,
            "evidence_item_count": evidence_item_count,
            "evidence_fingerprint": evidence_fingerprint,
        }

        if self._health == ProviderHealthStatus.UNAVAILABLE:
            self._failure_count += 1
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                finish_reason="error",
                error_code="PROVIDER_UNAVAILABLE",
                metadata={"safe_error": "Provider unavailable."},
            )

        if self._mode == "unavailable":
            self._failure_count += 1
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                finish_reason="error",
                error_code="PROVIDER_UNAVAILABLE",
                metadata={"safe_error": "Provider unavailable."},
            )

        if self._mode == "timeout":
            self._failure_count += 1
            raise TimeoutError("deterministic fake provider timeout")

        if self._mode == "malformed":
            self._failure_count += 1
            raise ValueError("deterministic fake provider malformed response")

        if self._mode == "error":
            self._failure_count += 1
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                finish_reason="error",
                error_code="PROVIDER_ERROR",
                metadata={"safe_error": "Provider execution error."},
            )

        if self._mode == "empty":
            self._failure_count += 1
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="OK",
                content="   ",
                finish_reason="stop",
                usage=ModelUsage(input_tokens=1, output_tokens=0),
                latency_ms=1,
                metadata={"fake": True},
            )

        forced_error = request.metadata.get("force_provider_error")
        if forced_error in (self.provider_id, "*"):
            self._failure_count += 1
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="ERROR",
                content="",
                finish_reason="error",
                error_code="PROVIDER_ERROR",
                metadata={"safe_error": "Provider execution error."},
            )

        forced_invalid = request.metadata.get("force_invalid_response")
        if forced_invalid in (self.provider_id, "*"):
            self._failure_count += 1
            return ModelResponse(
                provider_id=self.provider_id,
                model_id=model_id,
                status="OK",
                content="   ",
                finish_reason="stop",
                usage=ModelUsage(input_tokens=1, output_tokens=0),
                latency_ms=1,
                metadata={"fake": True},
            )

        self._success_count += 1
        return ModelResponse(
            provider_id=self.provider_id,
            model_id=model_id,
            status="OK",
            content=_deterministic_content(self.provider_id.upper(), request),
            finish_reason="stop",
            usage=ModelUsage(input_tokens=1, output_tokens=1),
            latency_ms=1,
            metadata={"fake": True},
        )


def build_default_fake_profiles() -> tuple[ModelProfile, ...]:
    return (
        ModelProfile(
            model_id="fake_fast:model",
            provider_id="fake_fast",
            display_name="Fake Fast Model",
            capabilities=(ModelCapability.CHAT, ModelCapability.REASONING),
            context_window=4096,
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
        ModelProfile(
            model_id="fake_frontier:model",
            provider_id="fake_frontier",
            display_name="Fake Frontier Model",
            capabilities=(
                ModelCapability.CHAT,
                ModelCapability.REASONING,
                ModelCapability.RESEARCH_SYNTHESIS,
                ModelCapability.LONG_CONTEXT,
            ),
            context_window=64000,
            supports_tools=False,
            supports_vision=False,
            supports_structured_output=True,
            local=False,
            privacy_class=PrivacyClass.REMOTE_ALLOWED,
            cost_class=CostClass.HIGH,
            latency_class=LatencyClass.NORMAL,
            quality_class=QualityClass.FRONTIER,
            enabled=True,
        ),
        ModelProfile(
            model_id="fake_reasoning:model",
            provider_id="fake_reasoning",
            display_name="Fake Reasoning Specialist",
            capabilities=(
                ModelCapability.REASONING,
                ModelCapability.DEEP_REASONING,
                ModelCapability.RESEARCH_SYNTHESIS,
            ),
            context_window=32000,
            supports_tools=False,
            supports_vision=False,
            supports_structured_output=True,
            local=False,
            privacy_class=PrivacyClass.PRIVATE_REMOTE_ALLOWED,
            cost_class=CostClass.MEDIUM,
            latency_class=LatencyClass.SLOW,
            quality_class=QualityClass.HIGH,
            enabled=True,
        ),
        ModelProfile(
            model_id="fake_coding:model",
            provider_id="fake_coding",
            display_name="Fake Coding Specialist",
            capabilities=(ModelCapability.CODING, ModelCapability.REASONING),
            context_window=16000,
            supports_tools=False,
            supports_vision=False,
            supports_structured_output=True,
            local=False,
            privacy_class=PrivacyClass.REMOTE_ALLOWED,
            cost_class=CostClass.MEDIUM,
            latency_class=LatencyClass.NORMAL,
            quality_class=QualityClass.HIGH,
            enabled=True,
        ),
    )


def build_default_fake_providers() -> tuple[DeterministicFakeProvider, ...]:
    providers = []
    for profile in build_default_fake_profiles():
        providers.append(
            DeterministicFakeProvider(
                _provider_id=profile.provider_id,
                _profile=profile,
            )
        )
    return tuple(providers)
