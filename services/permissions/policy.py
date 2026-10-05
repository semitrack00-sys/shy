from dataclasses import dataclass
from enum import Enum


class PermissionLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    SAFE_WRITE = "SAFE_WRITE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    FORBIDDEN = "FORBIDDEN"


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
class ToolPermission:
    tool_name: str
    risk: RiskLevel
    decision: Decision
    reason: str
    level: PermissionLevel = PermissionLevel.READ_ONLY


@dataclass(frozen=True)
class ToolPolicy(ToolPermission):
    pass


POLICIES = {
    "system.health": ToolPolicy(
        tool_name="system.health",
        risk=RiskLevel.LOW,
        decision=Decision.ALLOW,
        reason="Read-only health information.",
        level=PermissionLevel.READ_ONLY,
    ),
    "memory.read": ToolPolicy(
        tool_name="memory.read",
        risk=RiskLevel.LOW,
        decision=Decision.ALLOW,
        reason="Read-only access to authorized SHY memory.",
        level=PermissionLevel.READ_ONLY,
    ),
    "web.search": ToolPolicy(
        tool_name="web.search",
        risk=RiskLevel.LOW,
        decision=Decision.ALLOW,
        reason="Read-only public information retrieval.",
        level=PermissionLevel.READ_ONLY,
    ),
    "calculator": ToolPolicy(
        tool_name="calculator",
        risk=RiskLevel.LOW,
        decision=Decision.ALLOW,
        reason="Deterministic local arithmetic and percentage calculations.",
        level=PermissionLevel.READ_ONLY,
    ),
    "datetime.now": ToolPolicy(
        tool_name="datetime.now",
        risk=RiskLevel.LOW,
        decision=Decision.ALLOW,
        reason="Read-only system time information.",
        level=PermissionLevel.READ_ONLY,
    ),
    "file.read": ToolPolicy(
        tool_name="file.read",
        risk=RiskLevel.MEDIUM,
        decision=Decision.ALLOW,
        reason="Read-only access to approved SHY files only.",
        level=PermissionLevel.READ_ONLY,
    ),
    "database.read": ToolPolicy(
        tool_name="database.read",
        risk=RiskLevel.MEDIUM,
        decision=Decision.ALLOW,
        reason="Read-only access to approved database metadata and safe summaries.",
        level=PermissionLevel.READ_ONLY,
    ),
    "message.send": ToolPolicy(
        tool_name="message.send",
        risk=RiskLevel.CRITICAL,
        decision=Decision.DENY,
        reason="message.send is unavailable in SHY v0.13.",
        level=PermissionLevel.FORBIDDEN,
    ),
    "file.delete": ToolPolicy(
        tool_name="file.delete",
        risk=RiskLevel.CRITICAL,
        decision=Decision.DENY,
        reason="file.delete is unavailable in SHY v0.13.",
        level=PermissionLevel.FORBIDDEN,
    ),
    "production.deploy": ToolPolicy(
        tool_name="production.deploy",
        risk=RiskLevel.CRITICAL,
        decision=Decision.DENY,
        reason="production.deploy is unavailable in SHY v0.13.",
        level=PermissionLevel.FORBIDDEN,
    ),
    "money.spend": ToolPolicy(
        tool_name="money.spend",
        risk=RiskLevel.CRITICAL,
        decision=Decision.DENY,
        reason="money.spend is unavailable in SHY v0.13.",
        level=PermissionLevel.FORBIDDEN,
    ),
}


UNKNOWN_TOOL_POLICY = ToolPolicy(
    tool_name="unknown",
    risk=RiskLevel.CRITICAL,
    decision=Decision.DENY,
    reason="Unknown tools are denied by default.",
    level=PermissionLevel.FORBIDDEN,
)


def evaluate_tool(tool_name: str) -> ToolPolicy:
    """Return SHY's policy for a requested tool."""
    return POLICIES.get(tool_name, UNKNOWN_TOOL_POLICY)
