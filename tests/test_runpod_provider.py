"""Real transport contract using a local fixture transport; no billed GPU calls."""
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch
import httpx

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("shy_provider_runpod", ROOT / "services/model-router/app/providers/runpod.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
types = module._types.contracts_module


def run():
    captured = []
    real_client = httpx.Client
    def handle(request):
        import json
        captured.append((request.url, request.headers, json.loads(request.content)))
        return httpx.Response(200, json={"choices": [{"message": {"content": "Paris."}, "finish_reason": "stop"}]})
    with patch.dict(os.environ, {"SHY_RUNPOD_ENDPOINT_ID": "fixture123", "SHY_RUNPOD_API_KEY": "fixture-private-key", "SHY_MODEL_BACKEND": "runpod"}, clear=False):
        provider = module.RunPodProvider()
        assert provider.configured and not provider.last_generation_succeeded
        assert provider.list_models()[0].local is False
        assert provider.list_models()[0].privacy_class == types.PrivacyClass.REMOTE_ALLOWED
        request = types.ModelRequest(messages=(types.ModelMessage("user", "Capital of France?"),), capability=types.ModelCapability.CHAT, max_output_tokens=9000)
        with patch.object(module.httpx, "Client", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs)):
            response = provider.generate(request, provider.model_id)
            assert response.content == "Paris." and provider.last_generation_succeeded
            url, headers, payload = captured[0]
            assert str(url) == "https://api.runpod.ai/v2/fixture123/openai/v1/chat/completions"
            assert headers["Authorization"] == "Bearer fixture-private-key"
            assert payload["max_tokens"] == 512 and payload["stream"] is False
            assert payload["chat_template_kwargs"]["enable_thinking"] is False
            for privacy in ("LOCAL_ONLY", "PRIVATE_REMOTE_ALLOWED"):
                private = types.ModelRequest(messages=request.messages, capability=request.capability, metadata={"privacy_requirement": privacy})
                try:
                    provider.generate(private, provider.model_id)
                    raise AssertionError("Private request transmitted")
                except ValueError:
                    pass
            assert len(captured) == 1
        def fail(request):
            return httpx.Response(401, text="fixture-private-key secret")
        with patch.object(module.httpx, "Client", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(fail), **kwargs)):
            try:
                provider.generate(request, provider.model_id)
                raise AssertionError("Upstream failure accepted")
            except ValueError as exc:
                assert "fixture-private-key" not in str(exc) and "401" not in str(exc)
        assert not provider.last_generation_succeeded
        for bad_endpoint in ("../credentials", "https://evil.test", "fixture123?token=x"):
            with patch.dict(os.environ, {"SHY_RUNPOD_ENDPOINT_ID": bad_endpoint}):
                assert not module.RunPodProvider().configured
        router_spec = importlib.util.spec_from_file_location("shy_runpod_router_test", ROOT / "services/model-router/app/router.py")
        router_module = importlib.util.module_from_spec(router_spec)
        sys.modules[router_spec.name] = router_module
        router_spec.loader.exec_module(router_module)
        router = router_module.ModelRouter("qwen3.5:4b", include_fake_providers=False)
        decision = router.build_routing_decision("Hello", role=router_module.ModelRole.FAST)
        assert decision.selected_provider == "runpod"
        for privacy in (types.PrivacyClass.LOCAL_ONLY, types.PrivacyClass.PRIVATE_REMOTE_ALLOWED):
            assert router.build_routing_decision("Hello", role=router_module.ModelRole.FAST, privacy_requirement=privacy) is None
        with patch.dict(os.environ, {"SHY_RUNPOD_API_KEY": ""}):
            closed = router_module.ModelRouter("qwen3.5:4b", include_fake_providers=False)
            assert closed.build_routing_decision("Hello", role=router_module.ModelRole.FAST) is None
        with patch.dict(os.environ, {"SHY_MODEL_BACKEND": "ollama"}):
            local = router_module.ModelRouter("qwen3.5:4b", include_fake_providers=False)
            assert local.build_routing_decision("Hello", role=router_module.ModelRole.FAST).selected_provider == "ollama"
    print("RunPod transport, privacy, token bounds, secret redaction, and fixed-host checks passed")


if __name__ == "__main__":
    run()
