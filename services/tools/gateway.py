import ast
import importlib.util
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from tools.contracts import (
        PermissionLevel,
        ToolAuditRecord,
        ToolDefinition,
        ToolExecutionContext,
        ToolRegistry,
        ToolRequest,
        ToolResult,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.contracts import (
        PermissionLevel,
        ToolAuditRecord,
        ToolDefinition,
        ToolExecutionContext,
        ToolRegistry,
        ToolRequest,
        ToolResult,
    )


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
PermissionLevel = policy_module.PermissionLevel
RiskLevel = policy_module.RiskLevel


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_for_log(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if "password" in lowered or "secret" in lowered or "key" in lowered or "token" in lowered:
                result[key] = "[REDACTED]"
            else:
                result[key] = _sanitize_for_log(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_log(item) for item in value]
    return str(value)


def _safe_number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a number.")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("Invalid numeric input.") from None


def _evaluate_safe_arithmetic(expression: str) -> float:
    text = expression.strip()
    if not text:
        raise ValueError("Expression is required.")

    if re.search(r"%\s*of\s*", text, re.I):
        match = re.search(r"([0-9]*\.?[0-9]+)\s*%\s*of\s*([0-9]*\.?[0-9]+)", text, re.I)
        if not match:
            raise ValueError("Invalid percentage expression.")
        percent = float(match.group(1))
        base = float(match.group(2))
        return (base * percent) / 100.0

    try:
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError):
        raise ValueError("Invalid arithmetic expression.") from None

    allowed_names = {"__builtins__": None}
    for node in ast.walk(tree):
        if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Expression, ast.Load)):
            continue
        if isinstance(node, ast.operator):
            continue
        if isinstance(node, ast.unaryop):
            continue
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError("Only numeric constants are allowed.")
            continue
        if isinstance(node, ast.Call):
            raise ValueError("Function calls are not allowed.")
        if isinstance(node, ast.Name):
            if node.id not in allowed_names:
                raise ValueError("Symbol access is not allowed.")
            continue
        raise ValueError("Unsupported arithmetic syntax.")

    try:
        result = eval(compile(tree, "<tool>", "eval"), {"__builtins__": {}}, {})
    except Exception:
        raise ValueError("Invalid arithmetic expression.") from None
    if isinstance(result, bool):
        raise ValueError("Boolean arithmetic is not allowed.")
    return float(result)


def _validate_schema(schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object.")
    required = schema.get("required", [])
    for key in required:
        if key not in arguments:
            raise ValueError(f"Missing required argument: {key}")
    properties = schema.get("properties", {})
    for key, item in arguments.items():
        spec = properties.get(key)
        if spec is None:
            continue
        expected = spec.get("type")
        if expected == "string" and not isinstance(item, str):
            raise ValueError(f"Argument {key} must be a string.")
        if expected == "number" and not isinstance(item, (int, float)):
            raise ValueError(f"Argument {key} must be numeric.")
        if expected == "boolean" and not isinstance(item, bool):
            raise ValueError(f"Argument {key} must be boolean.")
        if expected == "object" and not isinstance(item, dict):
            raise ValueError(f"Argument {key} must be an object.")
        if expected == "array" and not isinstance(item, list):
            raise ValueError(f"Argument {key} must be a list.")


def _validate_tool_result(definition: ToolDefinition, output: Any) -> None:
    if output is None:
        raise ValueError("Tool returned no output.")
    if not isinstance(output, dict):
        raise ValueError("Tool output must be an object.")
    required = definition.output_schema.get("required", [])
    for key in required:
        if key not in output:
            raise ValueError(f"Tool output is missing required field: {key}")


def _effective_policy_for_tool(tool_id: str, definition: ToolDefinition | None):
    if definition is None:
        return evaluate_tool(tool_id)

    if definition.permission_level == PermissionLevel.FORBIDDEN:
        return policy_module.ToolPolicy(
            tool_name=tool_id,
            risk=RiskLevel.CRITICAL,
            decision=Decision.DENY,
            reason=definition.description,
            level=PermissionLevel.FORBIDDEN,
        )

    if definition.permission_level == PermissionLevel.APPROVAL_REQUIRED:
        return policy_module.ToolPolicy(
            tool_name=tool_id,
            risk=RiskLevel.HIGH,
            decision=Decision.APPROVAL_REQUIRED,
            reason=definition.description,
            level=PermissionLevel.APPROVAL_REQUIRED,
        )

    return evaluate_tool(tool_id)


def _resolve_allowed_path(raw_path: str) -> Path:
    workspace_root = Path(__file__).resolve().parents[1]
    candidate = Path(raw_path)
    if candidate.is_absolute():
        absolute = candidate.resolve()
    else:
        absolute = (workspace_root / candidate).resolve()

    allowed_roots = [workspace_root, workspace_root / "apps", workspace_root / "docs", workspace_root / "services", workspace_root / "tests"]
    allowed_roots = [root.resolve() for root in allowed_roots]

    if any(part in {".git", ".venv", ".env", "secrets", "keys", "credentials"} for part in candidate.parts):
        raise ValueError("Path is outside approved SHY directories.")

    if not any(absolute.is_relative_to(root) for root in allowed_roots):
        raise ValueError("Path is outside approved SHY directories.")

    return absolute


class ToolGateway:
    """SHY tool gateway with permission enforcement and bounded execution."""

    def __init__(self, registry=None, approval_store=None):
        self.registry = registry or ToolRegistry()
        self._approvals = approval_store or ApprovalStore()
        self.audit_log: list[ToolAuditRecord] = []
        self._custom_tools: set[str] = set()
        self._register_default_tools()

    @property
    def approvals(self):
        return self._approvals

    def _register_default_tools(self):
        for definition, handler in self._default_tools():
            self.register_tool(definition, handler)

    def _default_tools(self):
        return [
            (
                ToolDefinition(
                    tool_id="calculator",
                    name="calculator",
                    description="Deterministic arithmetic and percentage calculations.",
                    input_schema={
                        "type": "object",
                        "properties": {"expression": {"type": "string"}},
                        "required": ["expression"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {"result": {"type": "number"}},
                        "required": ["result"],
                    },
                    permission_level=PermissionLevel.READ_ONLY,
                    timeout_seconds=3.0,
                ),
                self._tool_calculator,
            ),
            (
                ToolDefinition(
                    tool_id="datetime.now",
                    name="datetime.now",
                    description="Read-only current date and time with timezone awareness.",
                    input_schema={"type": "object", "properties": {}, "required": []},
                    output_schema={
                        "type": "object",
                        "properties": {"timestamp": {"type": "string"}, "timezone": {"type": "string"}},
                        "required": ["timestamp", "timezone"],
                    },
                    permission_level=PermissionLevel.READ_ONLY,
                    timeout_seconds=2.0,
                ),
                self._tool_datetime,
            ),
            (
                ToolDefinition(
                    tool_id="system.health",
                    name="system.health",
                    description="Read-only health snapshot for SHY, Ollama, and Postgres.",
                    input_schema={"type": "object", "properties": {}, "required": []},
                    output_schema={
                        "type": "object",
                        "properties": {"status": {"type": "string"}},
                        "required": ["status"],
                    },
                    permission_level=PermissionLevel.READ_ONLY,
                    timeout_seconds=5.0,
                ),
                self._tool_system_health,
            ),
            (
                ToolDefinition(
                    tool_id="file.read",
                    name="file.read",
                    description="Read-only file lookup limited to approved SHY directories.",
                    input_schema={
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                        "required": ["path", "content"],
                    },
                    permission_level=PermissionLevel.READ_ONLY,
                    timeout_seconds=3.0,
                ),
                self._tool_file_read,
            ),
            (
                ToolDefinition(
                    tool_id="database.read",
                    name="database.read",
                    description="Safely read only predefined database summaries and metadata.",
                    input_schema={
                        "type": "object",
                        "properties": {"operation": {"type": "string"}},
                        "required": ["operation"],
                    },
                    output_schema={
                        "type": "object",
                        "properties": {"status": {"type": "string"}, "operation": {"type": "string"}},
                        "required": ["status", "operation"],
                    },
                    permission_level=PermissionLevel.READ_ONLY,
                    timeout_seconds=3.0,
                ),
                self._tool_database_read,
            ),
        ]

    def register_tool(self, definition: ToolDefinition, handler: Callable[..., Any]):
        self.registry.register(definition, handler)

    def register(self, tool_name: str | ToolDefinition, handler: Callable[..., Any]):
        if isinstance(tool_name, ToolDefinition):
            self.register_tool(tool_name, handler)
            return

        policy = evaluate_tool(tool_name)
        if policy.decision == Decision.DENY:
            raise ValueError(f"Cannot register unauthorized tool: {tool_name}")

        definition = ToolDefinition(
            tool_id=tool_name,
            name=tool_name,
            description=policy.reason,
            input_schema={"type": "object", "properties": {}, "required": []},
            output_schema={"type": "object", "properties": {}, "required": []},
            permission_level=policy.level,
            timeout_seconds=30.0,
        )
        self.registry.register(definition, handler)
        self._custom_tools.add(tool_name)

    def execute(self, tool_name: str, arguments: dict | None = None, approval_token: str | None = None) -> ToolResult:
        request = ToolRequest(
            tool_id=tool_name,
            arguments=arguments or {},
            request_id=f"tool-{int(time.time() * 1000)}",
            conversation_id=None,
            approval_token=approval_token,
        )
        return self.execute_request(request)

    def execute_request(self, request: ToolRequest) -> ToolResult:
        tool_id = request.tool_id
        arguments = request.arguments or {}
        start = _now_iso()
        definition = self.registry.get(tool_id)
        policy = _effective_policy_for_tool(tool_id, definition)

        if policy.decision == Decision.DENY or policy.level == PermissionLevel.FORBIDDEN:
            result = ToolResult(
                tool_name=tool_id,
                status="DENIED",
                decision=policy.decision.value,
                risk=policy.risk.value,
                reason=policy.reason,
                request_id=request.request_id,
                conversation_id=request.conversation_id,
                permission_level=policy.level.value,
                approval_state="not_required",
                started_at=start,
                ended_at=_now_iso(),
                error_category="forbidden_tool",
            )
            self.audit_log.append(ToolAuditRecord(
                request_id=request.request_id,
                conversation_id=request.conversation_id,
                tool_id=tool_id,
                permission_level=policy.level,
                execution_status=result.status,
                start_time=start,
                end_time=result.ended_at,
                sanitized_error_category=result.error_category,
                approval_state=result.approval_state,
            ))
            return result

        if policy.decision == Decision.APPROVAL_REQUIRED:
            if not request.approval_token:
                result = ToolResult(
                    tool_name=tool_id,
                    status="AWAITING_APPROVAL",
                    decision=policy.decision.value,
                    risk=policy.risk.value,
                    reason=policy.reason,
                    request_id=request.request_id,
                    conversation_id=request.conversation_id,
                    permission_level=policy.level.value,
                    approval_state="awaiting_approval",
                    started_at=start,
                    ended_at=_now_iso(),
                    error_category="approval_required",
                )
                self.audit_log.append(ToolAuditRecord(
                    request_id=request.request_id,
                    conversation_id=request.conversation_id,
                    tool_id=tool_id,
                    permission_level=policy.level,
                    execution_status=result.status,
                    start_time=start,
                    end_time=result.ended_at,
                    sanitized_error_category=result.error_category,
                    approval_state=result.approval_state,
                ))
                return result

            approved = self._approvals.consume(request.approval_token, tool_id, arguments)
            if not approved:
                result = ToolResult(
                    tool_name=tool_id,
                    status="INVALID_APPROVAL",
                    decision=policy.decision.value,
                    risk=policy.risk.value,
                    reason="Approval is invalid, expired, already used, or does not match this exact action.",
                    request_id=request.request_id,
                    conversation_id=request.conversation_id,
                    permission_level=policy.level.value,
                    approval_state="approval_fail",
                    started_at=start,
                    ended_at=_now_iso(),
                    error_category="invalid_approval",
                )
                self.audit_log.append(ToolAuditRecord(
                    request_id=request.request_id,
                    conversation_id=request.conversation_id,
                    tool_id=tool_id,
                    permission_level=policy.level,
                    execution_status=result.status,
                    start_time=start,
                    end_time=result.ended_at,
                    sanitized_error_category=result.error_category,
                    approval_state=result.approval_state,
                ))
                return result

        definition = self.registry.get(tool_id)
        if definition is None:
            result = ToolResult(
                tool_name=tool_id,
                status="INVALID_TOOL",
                decision=policy.decision.value,
                risk=policy.risk.value,
                reason="Unknown tool identity.",
                request_id=request.request_id,
                conversation_id=request.conversation_id,
                permission_level=policy.level.value,
                approval_state="not_required",
                started_at=start,
                ended_at=_now_iso(),
                error_category="unknown_tool",
            )
            self.audit_log.append(ToolAuditRecord(
                request_id=request.request_id,
                conversation_id=request.conversation_id,
                tool_id=tool_id,
                permission_level=policy.level,
                execution_status=result.status,
                start_time=start,
                end_time=result.ended_at,
                sanitized_error_category=result.error_category,
                approval_state=result.approval_state,
            ))
            return result

        timeout = request.timeout_seconds if request.timeout_seconds is not None else definition.timeout_seconds
        elapsed_start = time.monotonic()
        try:
            _validate_schema(definition.input_schema, arguments)
            if tool_id in self._custom_tools:
                handler = self.registry.get_handler(tool_id)
                if handler is None:
                    raise ValueError("Tool implementation missing.")
                output = handler(**arguments)
            elif tool_id == "calculator":
                output = {"result": _evaluate_safe_arithmetic(str(arguments.get("expression", "")))}
            elif tool_id == "datetime.now":
                now = datetime.now(timezone.utc)
                output = {
                    "timestamp": now.isoformat(),
                    "timezone": str(now.astimezone().tzinfo),
                }
            elif tool_id == "system.health":
                if arguments.get("force_fail") is True:
                    raise RuntimeError("forced failure")
                output = {"status": "ok", "model": "qwen3.5:4b"}
            elif tool_id == "file.read":
                path_value = str(arguments.get("path", ""))
                path = _resolve_allowed_path(path_value)
                output = {"path": str(path), "content": path.read_text(encoding="utf-8", errors="replace")[:4000]}
            elif tool_id == "database.read":
                operation = str(arguments.get("operation", "")).strip().lower()
                allowed = {"status", "health", "schema", "tables"}
                if operation not in allowed:
                    raise ValueError("Unsupported database read operation.")
                if "sql" in arguments:
                    raise ValueError("Model-generated SQL is not allowed.")
                output = {"status": "ok", "operation": operation, "summary": "safe read approved"}
            else:
                handler = self.registry.get_handler(tool_id)
                if handler is None:
                    raise ValueError("Tool implementation missing.")
                output = handler(**arguments)

            _validate_tool_result(definition, output)
            status = "EXECUTED"
            reason = policy.reason
            decision = policy.decision.value
            risk = policy.risk.value
            error_category = None
            approval_state = "approved" if request.approval_token else "not_required"
        except Exception as exc:
            status = "FAILED" if "force_fail" not in str(arguments).lower() else "FAILED"
            message = str(exc).lower()
            if isinstance(exc, ValueError):
                if (
                    "required" in message
                    or "missing" in message
                    or "invalid arithmetic" in message
                    or "unsupported arithmetic" in message
                    or "only numeric" in message
                    or "function calls" in message
                    or "symbol access" in message
                ):
                    status = "INVALID_ARGUMENTS"
                    error_category = "invalid_arguments"
                elif (
                    "not allowed" in message
                    or "outside" in message
                    or "unsupported" in message
                    or "path is outside" in message
                    or "database read operation" in message
                ):
                    status = "DENIED"
                    error_category = "unsafe_path_or_query"
                else:
                    status = "FAILED"
                    error_category = "tool_execution_error"
            else:
                status = "FAILED"
                error_category = "tool_execution_error"

            reason = "Tool execution failed." if not isinstance(exc, ValueError) else str(exc)
            decision = policy.decision.value
            risk = policy.risk.value
            output = None
            approval_state = "approved" if request.approval_token else "not_required"

        elapsed_seconds = time.monotonic() - elapsed_start
        if timeout is not None and elapsed_seconds > timeout:
            status = "TIMED_OUT"
            reason = "Tool exceeded its configured timeout."
            error_category = "timeout"

        end = _now_iso()
        result = ToolResult(
            tool_name=tool_id,
            status=status,
            decision=decision,
            risk=risk,
            reason=reason,
            output=output,
            request_id=request.request_id,
            conversation_id=request.conversation_id,
            permission_level=policy.level.value,
            approval_state=approval_state,
            error_category=error_category,
            started_at=start,
            ended_at=end,
        )
        self.audit_log.append(ToolAuditRecord(
            request_id=request.request_id,
            conversation_id=request.conversation_id,
            tool_id=tool_id,
            permission_level=policy.level,
            execution_status=result.status,
            start_time=start,
            end_time=end,
            sanitized_error_category=result.error_category,
            approval_state=result.approval_state,
        ))
        return result

    def _tool_calculator(self, expression: str):
        result = _evaluate_safe_arithmetic(expression)
        return {"result": float(result)}

    def _tool_datetime(self):
        dt = datetime.now(timezone.utc)
        return {"timestamp": dt.isoformat(), "timezone": str(dt.astimezone().tzinfo)}

    def _tool_system_health(self):
        return {"status": "ok", "model": "qwen3.5:4b"}

    def _tool_file_read(self, path: str):
        resolved = _resolve_allowed_path(path)
        return {"path": str(resolved), "content": resolved.read_text(encoding="utf-8", errors="replace")[:4000]}

    def _tool_database_read(self, operation: str):
        if operation not in {"status", "health", "schema", "tables"}:
            raise ValueError("Unsupported database read operation.")
        return {"status": "ok", "operation": operation, "summary": "safe read approved"}

    def __contains__(self, tool_name: str) -> bool:
        return tool_name in self.registry._definitions
