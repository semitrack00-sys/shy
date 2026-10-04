import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


services_path = Path(__file__).resolve().parents[1]
agent_runtime_path = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


planner_module = load_module(
    "shy_agent_planner",
    agent_runtime_path / "planner.py",
)

gateway_module = load_module(
    "shy_tool_gateway",
    services_path / "tools" / "gateway.py",
)

contracts_module = load_module(
    "shy_tool_contracts",
    services_path / "tools" / "contracts.py",
)

StepType = planner_module.StepType
AgentPlanner = planner_module.AgentPlanner
ToolGateway = gateway_module.ToolGateway
ToolRequest = contracts_module.ToolRequest


@dataclass
class AgentResult:
    status: str
    reason: str
    tool_name: str | None = None
    tool_status: str | None = None
    output: Any = None
    decision: str | None = None
    approval_state: str | None = None
    error_category: str | None = None


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

    def decide(self, message: str):
        return self.planner.decide(message)

    def build_task_plan(self, message: str, max_steps: int = 5, context: dict[str, Any] | None = None):
        return self.planner.build_task_plan(message, max_steps=max_steps, context=context)

    def execute_tool_step(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        conversation_id: str | None = None,
        request_id: str | None = None,
        approval_token: str | None = None,
        approval_scope: str | None = None,
        reason: str | None = None,
    ) -> AgentResult:
        result = self.gateway.execute_request(
            ToolRequest(
                tool_id=tool_name,
                arguments=arguments or {},
                conversation_id=conversation_id,
                request_id=request_id,
                approval_token=approval_token,
                metadata={"approval_scope": approval_scope} if approval_scope else {},
            )
        )

        return AgentResult(
            status="TOOL_RESULT",
            reason=reason or f"Executed task step via {tool_name}.",
            tool_name=result.tool_name,
            tool_status=result.status,
            output=result.output,
            decision=result.decision,
            approval_state=result.approval_state,
            error_category=result.error_category,
        )

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
                decision=result.decision,
                approval_state=result.approval_state,
                error_category=result.error_category,
            )

        return AgentResult(
            status="DENIED",
            reason="Unknown agent step type.",
        )
