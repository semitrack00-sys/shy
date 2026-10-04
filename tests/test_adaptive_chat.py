import importlib.util
import os
import sys
import types
from pathlib import Path


root = Path(__file__).resolve().parents[1]
services = root / "services"


for name in ("httpx", "psycopg", "fastapi", "pydantic"):
    if name in sys.modules:
        continue
    try:
        __import__(name)
    except ModuleNotFoundError:
        if name == "httpx":
            module = types.ModuleType("httpx")

            class _HTTPError(Exception):
                pass

            class _AsyncClient:
                def __init__(self, *args, **kwargs):
                    pass

                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return False

                async def get(self, *args, **kwargs):
                    raise _HTTPError("stubbed httpx client")

                async def post(self, *args, **kwargs):
                    raise _HTTPError("stubbed httpx client")

            module.HTTPError = _HTTPError
            module.AsyncClient = _AsyncClient
            sys.modules[name] = module
        elif name == "psycopg":
            module = types.ModuleType("psycopg")
            module.Error = type("PsycopgError", (Exception,), {})
            sys.modules[name] = module
        elif name == "fastapi":
            module = types.ModuleType("fastapi")

            class _HTTPException(Exception):
                def __init__(self, status_code, detail):
                    super().__init__(detail)
                    self.status_code = status_code
                    self.detail = detail

            class _FastAPI:
                def __init__(self, *args, **kwargs):
                    pass

                def on_event(self, *args, **kwargs):
                    def decorator(func):
                        return func

                    return decorator

                def get(self, *args, **kwargs):
                    def decorator(func):
                        return func

                    return decorator

                def post(self, *args, **kwargs):
                    def decorator(func):
                        return func

                    return decorator

            module.FastAPI = _FastAPI
            module.HTTPException = _HTTPException
            sys.modules[name] = module
        elif name == "pydantic":
            module = types.ModuleType("pydantic")

            class _BaseModel:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            module.BaseModel = _BaseModel
            sys.modules[name] = module


sys.path.insert(0, str(services))
sys.path.insert(0, str(services / "core"))

for package_name, package_path in (
    ("model_router", services / "model-router" / "app"),
    ("tools", services / "tools"),
    ("agent_runtime", services / "agent-runtime"),
    ("research", services / "research"),
):
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package


for module_name, module_path in (
    ("model_router.router", services / "model-router" / "app" / "router.py"),
    ("tools.gateway", services / "tools" / "gateway.py"),
    ("agent_runtime.runtime", services / "agent-runtime" / "runtime.py"),
    ("research.web_search", services / "research" / "web_search.py"),
    ("research.tavily", services / "research" / "tavily.py"),
    ("memory", services / "core" / "memory.py"),
):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


main_spec = importlib.util.spec_from_file_location("shy_core_adaptive_test", services / "core" / "main.py")
main = importlib.util.module_from_spec(main_spec)
main_spec.loader.exec_module(main)


assert hasattr(main, "decide_chat_response_mode")
assert hasattr(main, "apply_adaptive_response_policy")

assert main.decide_chat_response_mode("hi there") == "direct"
assert main.decide_chat_response_mode("Research the latest battery developments") == "research"
assert main.decide_chat_response_mode("Compare three constraints and produce a multi-step implementation plan") == "verify"

class DummyRoute:
    task_type = "general"
    reason = "simple"

class DummyResearchRoute:
    task_type = "research"
    reason = "research"

class DummyComplexRoute:
    task_type = "deep_reasoning"
    reason = "complex"

assert main.apply_adaptive_response_policy(DummyRoute(), "hi there") == "direct"
assert main.apply_adaptive_response_policy(DummyResearchRoute(), "research the latest AI trend") == "research"
assert main.apply_adaptive_response_policy(DummyComplexRoute(), "compare constraints and explain trade-offs") == "verify"

class FakeResearchProvider:
    name = "fake-provider"

    def search(self, query, max_results=5):
        return {
            "provider": "fake-provider",
            "query": query,
            "results": [
                {
                    "title": "Battery advance briefing",
                    "url": "https://example.com/battery-briefing",
                    "source": "example.org",
                    "snippet": "Next-generation battery chemistry improves cycle life and safety.",
                },
                {
                    "title": "Electrode material summary",
                    "url": "https://example.com/electrode-summary",
                    "source": "example.net",
                    "snippet": "Solid-state and lithium-silicon chemistries are reducing degradation.",
                },
            ],
        }

try:
    import asyncio

    main.research_service = FakeResearchProvider()

    async def _fake_generate_intelligence_response(message, history, route, generation_options=None):
        return "The latest evidence suggests battery advances focus on improved cycle life and safer chemistries. [1]"

    main.generate_intelligence_response = _fake_generate_intelligence_response

    async def _expect_research_pipeline():
        result = await main.run_research_pipeline("latest major developments in battery technology")
        assert len(result.evidence) >= 1
        assert result.status in {main.ResearchStatus.COMPLETE, main.ResearchStatus.PARTIAL}
        synthesis = await main.generate_research_response(
            "Research the latest major developments in battery technology.",
            research_result=result,
        )
        assert isinstance(synthesis, str)
        assert "cycle life" in synthesis.lower()
        assert "[1]" in synthesis

    asyncio.run(_expect_research_pipeline())

    async def _expect_research_failure():
        try:
            await main.generate_research_response(
                "Research the latest major developments in battery technology.",
                {"results": []},
            )
            raise AssertionError("Research with empty evidence should fail safely")
        except main.HTTPException as exc:
            assert "Research provider unavailable" in str(exc.detail)

    asyncio.run(_expect_research_failure())
except Exception as exc:
    raise AssertionError(f"research failure safeguard failed: {exc}") from exc

print("adaptive chat policy tests: PASS")
