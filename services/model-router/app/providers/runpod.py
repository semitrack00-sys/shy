"""Opt-in, bounded RunPod chat transport. No local-only data is accepted."""
import os
import re
import time
import httpx
import importlib.util
import sys
from pathlib import Path

_name = "shy_provider_ollama"
if _name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_name, Path(__file__).with_name("ollama.py"))
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
_types = sys.modules[_name]


class RunPodProvider(_types.ModelProvider):
    def __init__(self):
        self.endpoint_id = os.getenv("SHY_RUNPOD_ENDPOINT_ID", "").strip()
        self.api_key = os.getenv("SHY_RUNPOD_API_KEY", "").strip()
        self.model_id = os.getenv("SHY_RUNPOD_MODEL", "qwen/qwen3.5-4b").strip()
        self.configured = bool(re.fullmatch(r"[a-z0-9]{6,64}", self.endpoint_id) and self.api_key and self.model_id)
        self.last_generation_succeeded = False

    @property
    def provider_id(self):
        return "runpod"

    def health(self):
        return _types.ProviderHealth(
            provider_id=self.provider_id,
            status=(_types.ProviderHealthStatus.HEALTHY if self.last_generation_succeeded else
                    _types.ProviderHealthStatus.DEGRADED if self.configured else _types.ProviderHealthStatus.UNAVAILABLE),
            detail="Hosted model answered successfully." if self.last_generation_succeeded else "Hosted model configured; inference not yet verified." if self.configured else "Hosted model configuration missing.",
        )

    def list_models(self):
        if not self.model_id:
            return ()
        return (_types.ModelProfile(
            model_id=self.model_id, provider_id=self.provider_id,
            display_name="Qwen 3.5 4B (RunPod)",
            capabilities=(_types.ModelCapability.CHAT, _types.ModelCapability.REASONING,
                          _types.ModelCapability.CODING, _types.ModelCapability.RESEARCH_SYNTHESIS),
            context_window=4096, supports_tools=False, supports_vision=False,
            supports_structured_output=False, local=False,
            privacy_class=_types.PrivacyClass.REMOTE_ALLOWED,
            cost_class=_types.CostClass.LOW, latency_class=_types.LatencyClass.SLOW,
            quality_class=_types.QualityClass.STANDARD, enabled=self.configured,
        ),)

    def generate(self, request, model_id):
        self.last_generation_succeeded = False
        if not self.configured or model_id != self.model_id:
            raise ValueError("Hosted intelligence configuration unavailable.")
        privacy = str(request.metadata.get("privacy_requirement", "REMOTE_ALLOWED"))
        if privacy != "REMOTE_ALLOWED":
            raise ValueError("This request requires local intelligence.")
        messages = [{"role": item.role, "content": item.content} for item in request.messages]
        if any(item["role"] not in {"system", "user", "assistant"} or not isinstance(item["content"], str) for item in messages):
            raise ValueError("Hosted intelligence accepts text chat only.")
        if not messages or sum(len(item["content"]) for item in messages) > 12000:
            raise ValueError("Hosted intelligence context exceeds its limit.")
        tokens = min(512, max(1, int(request.max_output_tokens or 512)))
        payload = {"model": self.model_id, "messages": messages, "stream": False,
                   "max_tokens": tokens, "temperature": request.temperature if request.temperature is not None else 0.2,
                   "chat_template_kwargs": {"enable_thinking": False}}
        started = time.monotonic()
        try:
            # Fixed host, no redirects, no automatic retries that could multiply GPU charges.
            with httpx.Client(timeout=180.0, follow_redirects=False, trust_env=False) as client:
                response = client.post(f"https://api.runpod.ai/v2/{self.endpoint_id}/openai/v1/chat/completions",
                                       headers={"Authorization": f"Bearer {self.api_key}"}, json=payload)
                response.raise_for_status()
                result = response.json()
            choice = result["choices"][0]
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip() or len(content) > 32000:
                raise ValueError("Invalid hosted intelligence response.")
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            # Provider errors and URLs can contain sensitive details; never propagate their text.
            raise ValueError("Hosted intelligence unavailable or returned an invalid response.") from None
        self.last_generation_succeeded = True
        return _types.ModelResponse(provider_id=self.provider_id, model_id=self.model_id,
                                    status="OK", content=content.strip(),
                                    finish_reason=choice.get("finish_reason"),
                                    latency_ms=int((time.monotonic() - started) * 1000),
                                    metadata={"adapter": "runpod", "remote": True})
