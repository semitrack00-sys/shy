import importlib.util
from pathlib import Path


runtime_path = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "agent-runtime"
    / "runtime.py"
)

spec = importlib.util.spec_from_file_location(
    "shy_agent_runtime",
    runtime_path,
)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

gateway = module.ToolGateway()

execution_count = {"health": 0}


def health_tool():
    execution_count["health"] += 1
    return {
        "system": "SHY",
        "status": "healthy",
    }


gateway.register("system.health", health_tool)

runtime = module.AgentRuntime(gateway=gateway)


health = runtime.run("Check your health")

assert health.status == "TOOL_RESULT"
assert health.tool_name == "system.health"
assert health.tool_status == "EXECUTED"
assert health.output["system"] == "SHY"
assert execution_count["health"] == 1
print("planner -> runtime -> gateway: EXECUTED")


normal = runtime.run("Explain how rain forms")

assert normal.status == "RESPOND"
assert execution_count["health"] == 1
print("normal request: NO TOOL EXECUTION")


dangerous = runtime.run("Spend $500 for me")

assert dangerous.status == "RESPOND"
assert execution_count["health"] == 1
print("sensitive unimplemented request: NO EXECUTION")


unknown = runtime.run("Run super.secret.tool")

assert unknown.status == "RESPOND"
assert execution_count["health"] == 1
print("unknown request: NO EXECUTION")


print("SHY Agent Runtime tests: PASS")
