import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


policy_path = (
    Path(__file__).resolve().parents[1]
    / "permissions"
    / "policy.py"
)

spec = importlib.util.spec_from_file_location(
    "shy_permissions",
    policy_path,
)

policy_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy_module)

Decision = policy_module.Decision
evaluate_tool = policy_module.evaluate_tool


@dataclass
class ToolResult:
    tool_name: str
    status: str
    decision: str
    risk: str
    reason: str
    output: Any = None


class ToolGateway:
    """
    SHY Tool Gateway.

    Security invariants:
    - Every tool request passes through policy evaluation.
    - Unknown tools fail closed.
    - Approval-required tools do not execute automatically.
    - The model cannot approve its own actions.
    """

    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(
        self,
        tool_name: str,
        handler: Callable[..., Any],
    ):
        policy = evaluate_tool(tool_name)

        if policy.decision == Decision.DENY:
            raise ValueError(
                f"Cannot register unauthorized tool: {tool_name}"
            )

        self._tools[tool_name] = handler

    def execute(
        self,
        tool_name: str,
        arguments: dict | None = None,
        human_approved: bool = False,
    ) -> ToolResult:

        arguments = arguments or {}
        policy = evaluate_tool(tool_name)

        if policy.decision == Decision.DENY:
            return ToolResult(
                tool_name=tool_name,
                status="DENIED",
                decision=policy.decision.value,
                risk=policy.risk.value,
                reason=policy.reason,
            )

        if (
            policy.decision == Decision.APPROVAL_REQUIRED
            and not human_approved
        ):
            return ToolResult(
                tool_name=tool_name,
                status="AWAITING_APPROVAL",
                decision=policy.decision.value,
                risk=policy.risk.value,
                reason=policy.reason,
            )

        handler = self._tools.get(tool_name)

        if handler is None:
            return ToolResult(
                tool_name=tool_name,
                status="UNAVAILABLE",
                decision=policy.decision.value,
                risk=policy.risk.value,
                reason="Tool is authorized by policy but has no registered implementation.",
            )

        output = handler(**arguments)

        return ToolResult(
            tool_name=tool_name,
            status="EXECUTED",
            decision=policy.decision.value,
            risk=policy.risk.value,
            reason=policy.reason,
            output=output,
        )
