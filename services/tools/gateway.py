import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


services_path = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy_module = load_module(
    "shy_permissions",
    services_path / "permissions" / "policy.py",
)

approval_module = load_module(
    "shy_approvals",
    services_path / "permissions" / "approvals.py",
)

Decision = policy_module.Decision
evaluate_tool = policy_module.evaluate_tool
ApprovalStore = approval_module.ApprovalStore


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
    - Every request passes through policy evaluation.
    - Unknown tools fail closed.
    - Approval-required tools need a valid one-time approval.
    - Approval is bound to the exact tool and arguments.
    - Approval tokens are single-use and expire.
    - There is no boolean approval bypass.
    """

    def __init__(self, approval_store=None):
        self._tools: dict[str, Callable[..., Any]] = {}
        self._approvals = approval_store or ApprovalStore()

    @property
    def approvals(self):
        return self._approvals

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
        approval_token: str | None = None,
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

        if policy.decision == Decision.APPROVAL_REQUIRED:
            if approval_token is None:
                return ToolResult(
                    tool_name=tool_name,
                    status="AWAITING_APPROVAL",
                    decision=policy.decision.value,
                    risk=policy.risk.value,
                    reason=policy.reason,
                )

            approved = self._approvals.consume(
                approval_token,
                tool_name,
                arguments,
            )

            if not approved:
                return ToolResult(
                    tool_name=tool_name,
                    status="INVALID_APPROVAL",
                    decision=policy.decision.value,
                    risk=policy.risk.value,
                    reason="Approval is invalid, expired, already used, or does not match this exact action.",
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
