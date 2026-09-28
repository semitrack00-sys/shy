import importlib.util
from pathlib import Path


root = Path(__file__).resolve().parents[1]

runtime_path = (
    root
    / "services"
    / "agent-runtime"
    / "runtime.py"
)

research_path = (
    root
    / "services"
    / "research"
    / "web_search.py"
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime_module = load_module(
    "shy_agent_runtime",
    runtime_path,
)

research_module = load_module(
    "shy_web_search_runtime_test",
    research_path,
)

gateway = runtime_module.ToolGateway()

execution_count = {
    "health": 0,
    "web_search": 0,
}


def health_tool():
    execution_count["health"] += 1
    return {
        "system": "SHY",
        "status": "healthy",
    }


class FakeResearchProvider(
    research_module.WebSearchProvider
):
    name = "shy-test-research"

    def search(
        self,
        query,
        max_results=5,
    ):
        execution_count["web_search"] += 1

        return [
            research_module.SearchResult(
                title="NVIDIA Blackwell Test Source",
                url="https://example.com/nvidia-blackwell",
                snippet=(
                    "Structured test evidence for "
                    "SHY web research."
                ),
                source="example.com",
            )
        ]


research_service = research_module.WebSearchService(
    FakeResearchProvider()
)


gateway.register(
    "system.health",
    health_tool,
)

gateway.register(
    "web.search",
    research_service.search,
)


runtime = runtime_module.AgentRuntime(
    gateway=gateway
)


health = runtime.run(
    "Check your health"
)

assert health.status == "TOOL_RESULT"
assert health.tool_name == "system.health"
assert health.tool_status == "EXECUTED"
assert health.output["system"] == "SHY"
assert execution_count["health"] == 1

print(
    "planner -> runtime -> gateway: EXECUTED"
)


normal = runtime.run(
    "Explain how rain forms"
)

assert normal.status == "RESPOND"
assert execution_count["health"] == 1
assert execution_count["web_search"] == 0

print(
    "normal request: NO TOOL EXECUTION"
)


dangerous = runtime.run(
    "Spend $500 for me"
)

assert dangerous.status == "RESPOND"
assert execution_count["health"] == 1
assert execution_count["web_search"] == 0

print(
    "sensitive unimplemented request: NO EXECUTION"
)


unknown = runtime.run(
    "Run super.secret.tool"
)

assert unknown.status == "RESPOND"
assert execution_count["health"] == 1
assert execution_count["web_search"] == 0

print(
    "unknown request: NO EXECUTION"
)


research = runtime.run(
    "Research NVIDIA Blackwell"
)

assert research.status == "TOOL_RESULT"
assert research.tool_name == "web.search"
assert research.tool_status == "EXECUTED"

assert research.output["provider"] == (
    "shy-test-research"
)

assert research.output["query"] == (
    "NVIDIA Blackwell"
)

assert research.output["result_count"] == 1

assert (
    research.output["results"][0]["title"]
    == "NVIDIA Blackwell Test Source"
)

assert (
    research.output["results"][0]["url"]
    == "https://example.com/nvidia-blackwell"
)

assert execution_count["web_search"] == 1

print(
    "planner -> runtime -> gateway -> "
    "research: EXECUTED"
)

print(
    "structured research result: PASS"
)

print(
    "ordinary request isolation: PASS"
)

print(
    "SHY Agent Runtime tests: PASS"
)
