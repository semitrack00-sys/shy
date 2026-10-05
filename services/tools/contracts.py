from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PermissionLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    SAFE_WRITE = "SAFE_WRITE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    FORBIDDEN = "FORBIDDEN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class ToolPermission:
    level: PermissionLevel
    reason: str = ""
    requires_approval: bool = False


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permission_level: PermissionLevel
    timeout_seconds: float = 15.0
    deterministic_error_contract: str = "Structured error object with status, reason, and sanitized error category."
    examples: tuple[str, ...] = ()


@dataclass
class ToolRequest:
    tool_id: str
    arguments: dict[str, Any] | None = None
    conversation_id: str | None = None
    request_id: str | None = None
    approval_token: str | None = None
    timeout_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolExecutionContext:
    request_id: str | None
    conversation_id: str | None
    tool_id: str
    permission_level: PermissionLevel
    started_at: str
    approval_state: str = "not_required"


@dataclass
class ToolResult:
    tool_name: str
    status: str
    decision: str
    risk: str
    reason: str
    output: Any = None
    request_id: str | None = None
    conversation_id: str | None = None
    permission_level: str | None = None
    approval_state: str = "not_required"
    error_category: str | None = None
    started_at: str | None = None
    ended_at: str | None = None


@dataclass(frozen=True)
class ToolAuditRecord:
    request_id: str | None
    conversation_id: str | None
    tool_id: str
    permission_level: PermissionLevel
    execution_status: str
    start_time: str
    end_time: str
    sanitized_error_category: str | None = None
    approval_state: str = "not_required"


class ToolRegistry:
    def __init__(self):
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Any] = {}

    def register(self, definition: ToolDefinition, handler: Any):
        self._definitions[definition.tool_id] = definition
        self._handlers[definition.tool_id] = handler

    def get(self, tool_id: str) -> ToolDefinition | None:
        return self._definitions.get(tool_id)

    def get_handler(self, tool_id: str) -> Any:
        return self._handlers.get(tool_id)

    def route_tool(self, message: str) -> str | None:
        content = (message or "").strip().lower()
        if not content:
            return None

        if any(keyword in content for keyword in ("percent", "percentage", "%", "calculate", "arithmetic", "sum", "total", "minus", "plus", "multiply", "divide")):
            if re.search(r"\d", content):
                return "calculator"

        health_markers = (
            "system health",
            "shy health",
            "health status",
            "database connected",
            "database status",
            "ollama",
            "check your health",
            "is shy database connected",
        )
        if any(marker in content for marker in health_markers):
            return "system.health"

        file_markers = (
            "read file",
            "open file",
            "show file",
            "lookup file",
            "read from",
            "view file",
        )
        if any(marker in content for marker in file_markers):
            return "file.read"

        db_markers = (
            "database read",
            "db read",
            "read database",
            "query database",
            "recent conversations",
            "list tables",
            "database status",
        )
        if any(marker in content for marker in db_markers):
            return "database.read"

        return None
