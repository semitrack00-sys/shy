from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    ALLOW = "ALLOW"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DENY = "DENY"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ToolPolicy:
    tool_name: str
    risk: RiskLevel
    decision: Decision
    reason: str


POLICIES = {
    # Safe, read-only operations
    "system.health": ToolPolicy(
        tool_name="system.health",
        risk=RiskLevel.LOW,
        decision=Decision.ALLOW,
        reason="Read-only health information.",
    ),
    "memory.read": ToolPolicy(
        tool_name="memory.read",
        risk=RiskLevel.LOW,
        decision=Decision.ALLOW,
        reason="Read-only access to authorized SHY memory.",
    ),
    "web.search": ToolPolicy(
        tool_name="web.search",
        risk=RiskLevel.LOW,
        decision=Decision.ALLOW,
        reason="Read-only public information retrieval.",
    ),

    # External side effects require human approval
    "message.send": ToolPolicy(
        tool_name="message.send",
        risk=RiskLevel.HIGH,
        decision=Decision.APPROVAL_REQUIRED,
        reason="Sending a message creates an external side effect.",
    ),
    "file.delete": ToolPolicy(
        tool_name="file.delete",
        risk=RiskLevel.HIGH,
        decision=Decision.APPROVAL_REQUIRED,
        reason="Deleting data is destructive.",
    ),
    "production.deploy": ToolPolicy(
        tool_name="production.deploy",
        risk=RiskLevel.CRITICAL,
        decision=Decision.APPROVAL_REQUIRED,
        reason="Production deployment can affect live systems.",
    ),
    "money.spend": ToolPolicy(
        tool_name="money.spend",
        risk=RiskLevel.CRITICAL,
        decision=Decision.APPROVAL_REQUIRED,
        reason="Financial transactions require explicit human approval.",
    ),
}


UNKNOWN_TOOL_POLICY = ToolPolicy(
    tool_name="unknown",
    risk=RiskLevel.CRITICAL,
    decision=Decision.DENY,
    reason="Unknown tools are denied by default.",
)


def evaluate_tool(tool_name: str) -> ToolPolicy:
    """
    Return SHY's policy for a requested tool.

    Security invariant:
    Unknown tools fail closed and are denied.
    """
    return POLICIES.get(tool_name, UNKNOWN_TOOL_POLICY)
