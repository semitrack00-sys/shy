import importlib.util
from pathlib import Path


planner_path = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "agent-runtime"
    / "planner.py"
)

spec = importlib.util.spec_from_file_location(
    "shy_agent_planner",
    planner_path,
)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

planner = module.AgentPlanner()


health = planner.plan("Check your health")

assert health.step_type == module.StepType.TOOL
assert health.tool_name == "system.health"
assert health.arguments == {}
print("health request: TOOL -> system.health")


normal = planner.plan("Explain how rain forms")

assert normal.step_type == module.StepType.RESPOND
assert normal.tool_name is None
print("normal request: RESPOND")


dangerous = planner.plan("Spend $500 for me")

assert dangerous.step_type == module.StepType.RESPOND
assert dangerous.tool_name is None
print("unimplemented sensitive action: NOT PLANNED")


unknown = planner.plan("Run super.secret.tool")

assert unknown.step_type == module.StepType.RESPOND
assert unknown.tool_name is None
print("unknown tool request: NOT PLANNED")


print("SHY Agent Planner tests: PASS")
