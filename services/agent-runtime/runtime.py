import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any


services_path = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner_module = load_module(
    "shy_agent_planner",
    services_path / "agent-runtime" / "planner.py",
)

gateway_module = load_module(
    "shy_tool_gateway",
    services_path / "tools" / "gateway.py",
)

StepType = planner_module.StepType
AgentPlanner = planner_module.AgentPlanner
ToolGateway = gateway_module.ToolGateway


@dataclass
class AgentResult:
    status: str
    reason: str
    tool_name: str | None = None
    tool_status: str | None = None
    output: Any = None


class AgentRuntime:
    """
    SHY Agent Runtime v0.7.

    Planner proposes actions.
    Runtime coordinates actions.
    Tool Gateway remains the execution authority.
    """

    def __init__(self, planner=None, gateway=None):
        self.planner = planner or AgentPlanner()
        self.gateway = gateway or ToolGateway()

    def run(self, message: str) -> AgentResult:
        step = self.planner.plan(message)

        if step.step_type == StepType.RESPOND:
            return AgentResult(
                status="RESPOND",
                reason=step.reason,
            )

        if step.step_type == StepType.TOOL:
            result = self.gateway.execute(
                step.tool_name,
                step.arguments or {},
            )

            return AgentResult(
                status="TOOL_RESULT",
                reason=step.reason,
                tool_name=result.tool_name,
                tool_status=result.status,
                output=result.output,
            )

        return AgentResult(
            status="DENIED",
            reason="Unknown agent step type.",
        )
