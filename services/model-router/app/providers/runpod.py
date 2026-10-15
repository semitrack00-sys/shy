"""Opt-in, bounded RunPod chat transport. No local-only data is accepted."""
import os
import re
import time
import httpx
import importlib.util
import sys
import threading
from pathlib import Path

_name = "shy_provider_ollama"
if _name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_name, Path(__file__).with_name("ollama.py"))
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _module
    _spec.loader.exec_module(_module)
_types = sys.modules[_name]


class HostedInferenceError(ValueError):
    MESSAGES = {
        "busy": "SHY is already answering another cloud request. Please wait for it to finish.",
        "timeout": "The cloud model did not finish starting or answering in time. Please try again.",
        "unavailable": "Hosted intelligence is temporarily unavailable. Please try again shortly.",
    }

    def __init__(self, code):
        self.code = code
        super().__init__(self.MESSAGES[code])


class RunPodProvider(_types.ModelProvider):
    WAIT_SECONDS = 280.0
    POLL_SECONDS = 2.0

    def __init__(self):
        self.mode = os.getenv("SHY_RUNPOD_MODE", "dedicated").strip()
        self.endpoint_id = os.getenv("SHY_RUNPOD_ENDPOINT_ID", "").strip()
        self.api_key = os.getenv("SHY_RUNPOD_API_KEY", "").strip()
        self.model_id = os.getenv("SHY_RUNPOD_MODEL", "qwen/qwen3.5-4b").strip()
        self.configured = bool(re.fullmatch(r"[a-z0-9]{6,64}", self.endpoint_id) and self.api_key and self.model_id)
        if self.mode == "public":
            self.model_id = "Qwen/Qwen3-32B-AWQ"
            self.configured = bool(self.api_key)
        elif self.mode != "dedicated":
            self.configured = False
        self.last_generation_succeeded = False
        self.retry_at = 0.0
        self._generation_lock = threading.Lock()

    @property
    def retry_ready(self):
        return self.configured and time.monotonic() >= self.retry_at

    @staticmethod
    def public_error(exc):
        return str(exc) if isinstance(exc, HostedInferenceError) else None

    @property
    def provider_id(self):
        return "runpod"

    def health(self):
        return _types.ProviderHealth(
            provider_id=self.provider_id,
            status=(_types.ProviderHealthStatus.HEALTHY if self.last_generation_succeeded else
                    _types.ProviderHealthStatus.DEGRADED if self.retry_ready else _types.ProviderHealthStatus.UNAVAILABLE),
            detail="Hosted model answered successfully." if self.last_generation_succeeded else "Hosted model configured; inference not yet verified." if self.configured else "Hosted model configuration missing.",
        )

    def list_models(self):
        if not self.model_id:
            return ()
        return (_types.ModelProfile(
            model_id=self.model_id, provider_id=self.provider_id,
            display_name="Qwen 3 32B (RunPod public)" if self.mode == "public" else "Qwen 3.5 4B (RunPod)",
            capabilities=(_types.ModelCapability.CHAT, _types.ModelCapability.REASONING,
                          _types.ModelCapability.CODING, _types.ModelCapability.RESEARCH_SYNTHESIS),
            context_window=4096, supports_tools=False, supports_vision=False,
            supports_structured_output=False, local=False,
            privacy_class=_types.PrivacyClass.REMOTE_ALLOWED,
            cost_class=_types.CostClass.MEDIUM if self.mode == "public" else _types.CostClass.LOW,
            latency_class=_types.LatencyClass.NORMAL if self.mode == "public" else _types.LatencyClass.SLOW,
            quality_class=_types.QualityClass.STANDARD, enabled=self.configured,
        ),)

    def generate(self, request, model_id):
        if not self._generation_lock.acquire(blocking=False):
            raise HostedInferenceError("busy")
        try:
            if not self.retry_ready:
                raise HostedInferenceError("unavailable")
            return self._generate(request, model_id)
        finally:
            self._generation_lock.release()

    def _submit_and_wait(self, payload):
        base = f"https://api.runpod.ai/v2/{self.endpoint_id}"
        deadline = time.monotonic() + self.WAIT_SECONDS
        job_id = None
        terminal = False
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=20.0, follow_redirects=False, trust_env=False) as client:
            try:
                # Submit exactly once. Status polling never creates another billed job.
                response = client.post(base + "/run", headers=headers, json={
                    "input": {"openai_route": "/v1/chat/completions", "openai_input": payload},
                    "policy": {"executionTimeout": 180000, "ttl": 285000},
                })
                response.raise_for_status()
                result = response.json()
                job_id = result.get("id")
                if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", job_id):
                    job_id = None
                    raise HostedInferenceError("unavailable")
                while True:
                    status = result.get("status")
                    if status in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}:
                        terminal = True
                        if status != "COMPLETED":
                            raise HostedInferenceError("timeout" if status == "TIMED_OUT" else "unavailable")
                        output = result.get("output")
                        if isinstance(output, list) and len(output) == 1:
                            output = output[0]
                        if not isinstance(output, dict):
                            raise HostedInferenceError("unavailable")
                        return output
                    if status not in {"IN_QUEUE", "IN_PROGRESS"}:
                        raise HostedInferenceError("unavailable")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise HostedInferenceError("timeout")
                    time.sleep(min(self.POLL_SECONDS, remaining))
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise HostedInferenceError("timeout")
                    response = client.get(base + "/status/" + job_id, headers=headers,
                                          timeout=min(20.0, remaining))
                    response.raise_for_status()
                    result = response.json()
            except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
                if job_id and not terminal:
                    try:
                        # Best effort cancellation; the short server TTL is the backstop.
                        client.post(base + "/cancel/" + job_id, headers=headers, timeout=3.0)
                    except httpx.HTTPError:
                        pass
                code = exc.code if isinstance(exc, HostedInferenceError) else "timeout" if isinstance(exc, httpx.TimeoutException) else "unavailable"
                raise HostedInferenceError(code) from None

    def _public_completion(self, payload):
        # Fixed provider/model allowlist. One paid submission, no automatic retries
        # or fallback to a dedicated worker with a minutes-long cold start.
        with httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0),
                          follow_redirects=False, trust_env=False) as client:
            try:
                response = client.post(
                    "https://api.runpod.ai/v2/qwen3-32b-awq/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"}, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException:
                raise HostedInferenceError("timeout") from None

    def _generate(self, request, model_id):
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
            result = self._public_completion(payload) if self.mode == "public" else self._submit_and_wait(payload)
            choice = result["choices"][0]
            content = choice["message"]["content"]
            if self.mode == "public" and isinstance(content, str):
                # Some Qwen templates include an empty reasoning delimiter even
                # with thinking disabled. Never display a reasoning preamble.
                if "</think>" in content:
                    content = content.split("</think>", 1)[1]
                elif "<think>" in content:
                    raise ValueError("Incomplete hosted intelligence response.")
            if not isinstance(content, str) or not content.strip() or len(content) > 32000:
                raise ValueError("Invalid hosted intelligence response.")
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            # Provider errors and URLs can contain sensitive details; never propagate their text.
            self.retry_at = time.monotonic() + 30.0
            raise HostedInferenceError(exc.code if isinstance(exc, HostedInferenceError) else "unavailable") from None
        self.last_generation_succeeded = True
        self.retry_at = 0.0
        return _types.ModelResponse(provider_id=self.provider_id, model_id=self.model_id,
                                    status="OK", content=content.strip(),
                                    finish_reason=choice.get("finish_reason"),
                                    latency_ms=int((time.monotonic() - started) * 1000),
                                    metadata={"adapter": "runpod", "remote": True})
