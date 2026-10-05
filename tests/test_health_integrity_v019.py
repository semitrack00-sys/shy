import importlib.util
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "services" / "core"

os.environ.setdefault("DATABASE_URL", "postgresql://shy:shy_local_dev@127.0.0.1:5432/shy")
os.environ.setdefault("SHY_LOCAL_MODEL", "qwen3.5:4b")

spec = importlib.util.spec_from_file_location("shy_core_health_integrity_v019", CORE / "main.py")
main = importlib.util.module_from_spec(spec)
sys.modules["shy_core_health_integrity_v019"] = main
spec.loader.exec_module(main)


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


class FakeResponse:
    def __init__(self, *, success: bool, models: list[dict] | None = None):
        self.is_success = success
        self._models = list(models or [])

    def json(self):
        return {"models": self._models}


class FakeClient:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url):
        if self.error is not None:
            raise self.error
        return self.response


original_client = main.httpx.Client

try:
    main.httpx.Client = lambda timeout=5.0: FakeClient(
        error=main.httpx.HTTPError("ollama offline")
    )
    offline = main._collect_runtime_health_snapshot()
    _assert(offline["database_connected"] is True, "test database must be connected")
    _assert(offline["ollama_connected"] is False, "offline Ollama must be reported offline")
    _assert(offline["local_model_available"] is False, "model cannot be available when Ollama is offline")
    _assert(offline["application_healthy"] is False, "application cannot be healthy when Ollama is offline")
    _assert(offline["status"] == "degraded", "offline inference must degrade health")
    print("offline Ollama health truthfulness: PASS")

    main.httpx.Client = lambda timeout=5.0: FakeClient(
        response=FakeResponse(
            success=True,
            models=[{"name": "llama3.2:latest", "model": "llama3.2:latest"}],
        )
    )
    wrong_model = main._collect_runtime_health_snapshot()
    _assert(wrong_model["ollama_connected"] is True, "reachable Ollama must be reported connected")
    _assert(wrong_model["local_model_available"] is False, "configured model must be verified from Ollama tags")
    _assert(wrong_model["application_healthy"] is False, "wrong installed model cannot report healthy")
    _assert(wrong_model["status"] == "degraded", "missing configured model must degrade health")
    print("configured-model mismatch health truthfulness: PASS")

    main.httpx.Client = lambda timeout=5.0: FakeClient(
        response=FakeResponse(
            success=True,
            models=[{"name": "qwen3.5:4b", "model": "qwen3.5:4b"}],
        )
    )
    ready = main._collect_runtime_health_snapshot()
    _assert(ready["ollama_connected"] is True, "Ollama must be connected")
    _assert(ready["local_model_available"] is True, "configured model must be available")
    _assert(ready["database_connected"] is True, "database must be connected")
    _assert(ready["application_healthy"] is True, "all required local services should report healthy")
    _assert(ready["status"] == "ok", "healthy runtime status must be ok")
    print("reachable configured model health truthfulness: PASS")
finally:
    main.httpx.Client = original_client


print("SHY v0.19 health integrity gate: PASS")
