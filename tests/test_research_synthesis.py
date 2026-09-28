import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace


root = Path(__file__).resolve().parents[1]
services = root / "services"

sys.path.insert(0, str(services))
sys.path.insert(0, str(services / "core"))

# Reproduce the package layout created by the production Docker image.
import types

model_router_package = types.ModuleType("model_router")
model_router_package.__path__ = []
sys.modules["model_router"] = model_router_package

router_path = services / "model-router" / "app" / "router.py"
router_spec = importlib.util.spec_from_file_location(
    "model_router.router",
    router_path,
)
router_module = importlib.util.module_from_spec(router_spec)
sys.modules["model_router.router"] = router_module
router_spec.loader.exec_module(router_module)

# The source directory is named agent-runtime, while production Docker
# exposes it as the agent_runtime package.
agent_runtime_package = types.ModuleType("agent_runtime")
agent_runtime_package.__path__ = []
sys.modules["agent_runtime"] = agent_runtime_package

for module_name in ("planner", "runtime"):
    module_path = services / "agent-runtime" / f"{module_name}.py"
    module_spec = importlib.util.spec_from_file_location(
        f"agent_runtime.{module_name}",
        module_path,
    )
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[f"agent_runtime.{module_name}"] = module
    module_spec.loader.exec_module(module)

# Prevent creation of the real Tavily provider during module import.
os.environ.pop("TAVILY_API_KEY", None)

core_path = services / "core" / "main.py"

spec = importlib.util.spec_from_file_location(
    "shy_core_research_test",
    core_path,
)

core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class FakeRuntime:
    def __init__(self, result):
        self.result = result

    def run(self, message):
        return self.result


successful_result = SimpleNamespace(
    status="TOOL_RESULT",
    reason="Read-only public information retrieval.",
    tool_name="web.search",
    tool_status="EXECUTED",
    output={
        "provider": "fake-research",
        "query": "NVIDIA Blackwell",
        "result_count": 2,
        "results": [
            {
                "title": "Source One",
                "url": "https://example.com/one",
                "snippet": "Evidence one.",
                "source": "example.com",
            },
            {
                "title": "Source Two",
                "url": "https://example.org/two",
                "snippet": "Evidence two.",
                "source": "example.org",
            },
        ],
    },
)

core.agent_runtime = FakeRuntime(successful_result)

synthesis_calls = []


async def fake_generate_research_response(message, research_output):
    synthesis_calls.append(
        {
            "message": message,
            "research_output": research_output,
        }
    )
    return "Synthesized answer with evidence [1] [2]."


core.generate_research_response = fake_generate_research_response

response = asyncio.run(
    core.agent(
        core.AgentRequest(
            message="Research NVIDIA Blackwell"
        )
    )
)

assert response["assistant"] == "SHY"
assert response["status"] == "RESPOND"
assert response["message"] == (
    "Synthesized answer with evidence [1] [2]."
)
assert response["tool_name"] == "web.search"
assert response["tool_status"] == "EXECUTED"
assert response["research_provider"] == "fake-research"

assert response["sources"] == [
    {
        "number": 1,
        "title": "Source One",
        "url": "https://example.com/one",
        "source": "example.com",
    },
    {
        "number": 2,
        "title": "Source Two",
        "url": "https://example.org/two",
        "source": "example.org",
    },
]

assert len(synthesis_calls) == 1
assert synthesis_calls[0]["message"] == (
    "Research NVIDIA Blackwell"
)

print("successful research -> synthesis: PASS")
print("deterministic research sources: PASS")


failed_result = SimpleNamespace(
    status="TOOL_RESULT",
    reason="Tool execution failed.",
    tool_name="web.search",
    tool_status="FAILED",
    output=None,
)

core.agent_runtime = FakeRuntime(failed_result)

response = asyncio.run(
    core.agent(
        core.AgentRequest(
            message="Research unavailable subject"
        )
    )
)

assert response["status"] == "TOOL_RESULT"
assert response["tool_name"] == "web.search"
assert response["tool_status"] == "FAILED"
assert response["output"] is None

# The failed search must not have triggered another synthesis call.
assert len(synthesis_calls) == 1

print("failed research -> no synthesis: PASS")
print("SHY v0.9 research synthesis regression tests: PASS")
