import importlib.util
import json
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
services = root / "services"

sys.path.insert(0, str(services))
sys.path.insert(0, str(services / "core"))

for package_name, package_path in (
    ("tools", services / "tools"),
    ("permissions", services / "permissions"),
):
    package = __import__("types").ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package

for module_name, module_path in (
    ("tools.contracts", services / "tools" / "contracts.py"),
    ("tools.gateway", services / "tools" / "gateway.py"),
    ("permissions.policy", services / "permissions" / "policy.py"),
    ("permissions.approvals", services / "permissions" / "approvals.py"),
):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

contracts = sys.modules["tools.contracts"]
permissions = sys.modules["permissions.policy"]
gateway_module = sys.modules["tools.gateway"]

ToolGateway = gateway_module.ToolGateway
ToolResult = gateway_module.ToolResult
ToolRequest = contracts.ToolRequest
ToolDefinition = contracts.ToolDefinition
PermissionLevel = contracts.PermissionLevel
ToolPermission = contracts.ToolPermission
ToolAuditRecord = contracts.ToolAuditRecord
ToolRegistry = contracts.ToolRegistry

registry = ToolRegistry()

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "core"))

for package_name, package_path in (
    ("model_router", Path(__file__).resolve().parents[1] / "services" / "model-router" / "app"),
    ("tools", Path(__file__).resolve().parents[1] / "services" / "tools"),
    ("agent_runtime", Path(__file__).resolve().parents[1] / "services" / "agent-runtime"),
    ("research", Path(__file__).resolve().parents[1] / "services" / "research"),
    ("memory", Path(__file__).resolve().parents[1] / "services" / "core"),
):
    package = __import__("types").ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package

for module_name, module_path in (
    ("model_router.router", Path(__file__).resolve().parents[1] / "services" / "model-router" / "app" / "router.py"),
    ("tools.gateway", Path(__file__).resolve().parents[1] / "services" / "tools" / "gateway.py"),
    ("agent_runtime.runtime", Path(__file__).resolve().parents[1] / "services" / "agent-runtime" / "runtime.py"),
    ("research.web_search", Path(__file__).resolve().parents[1] / "services" / "research" / "web_search.py"),
    ("research.tavily", Path(__file__).resolve().parents[1] / "services" / "research" / "tavily.py"),
    ("memory", Path(__file__).resolve().parents[1] / "services" / "core" / "memory.py"),
):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


def _sum_handler(a: int, b: int):
    return {"result": a + b}


def _calc_percent_handler(value: float, percent: float):
    return {"result": (value * percent) / 100.0}


def _echo_handler(value):
    return {"value": value}


def _slow_handler():
    time.sleep(0.2)
    return {"value": "slow"}


def _bad_handler():
    raise RuntimeError("boom")


registry.register(
    ToolDefinition(
        tool_id="calculator",
        name="calculator",
        description="Deterministic arithmetic and percent calculations.",
        input_schema={"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]},
        output_schema={"type": "object", "properties": {"result": {"type": "number"}}, "required": ["result"]},
        permission_level=PermissionLevel.READ_ONLY,
        timeout_seconds=3.0,
    ),
    _echo_handler,
)

registry.register(
    ToolDefinition(
        tool_id="system.health",
        name="system.health",
        description="Read-only system health snapshot.",
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
        permission_level=PermissionLevel.READ_ONLY,
        timeout_seconds=5.0,
    ),
    lambda: {"status": "ok"},
)

registry.register(
    ToolDefinition(
        tool_id="forbidden.tool",
        name="forbidden.tool",
        description="Blocked-by-policy example.",
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        permission_level=PermissionLevel.FORBIDDEN,
        timeout_seconds=2.0,
    ),
    _echo_handler,
)

registry.register(
    ToolDefinition(
        tool_id="approval.tool",
        name="approval.tool",
        description="Approval-required example.",
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        permission_level=PermissionLevel.APPROVAL_REQUIRED,
        timeout_seconds=2.0,
    ),
    _echo_handler,
)

gateway = ToolGateway(registry=registry)

assert registry.route_tool("What is 17% of 842?") == "calculator"
assert registry.route_tool("Is SHY database connected?") == "system.health"
assert registry.route_tool("Explain photosynthesis.") is None

calc_request = ToolRequest(
    tool_id="calculator",
    arguments={"expression": "17% of 842"},
    conversation_id="conv-1",
    request_id="req-1",
)
calc_result = gateway.execute_request(calc_request)
assert calc_result.status == "EXECUTED"
assert calc_result.output["result"] == 143.14

bad_request = ToolRequest(tool_id="calculator", arguments={"expression": "DROP TABLE users;"}, conversation_id="conv-2", request_id="req-2")
assert gateway.execute_request(bad_request).status == "INVALID_ARGUMENTS"

invalid_tool = gateway.execute_request(ToolRequest(tool_id="missing.tool", arguments={}, conversation_id="conv-3", request_id="req-3"))
assert invalid_tool.status in {"INVALID_TOOL", "DENIED"}

approval_result = gateway.execute_request(ToolRequest(tool_id="approval.tool", arguments={}, conversation_id="conv-4", request_id="req-4"))
assert approval_result.status == "AWAITING_APPROVAL"

forbidden_result = gateway.execute_request(ToolRequest(tool_id="forbidden.tool", arguments={}, conversation_id="conv-5", request_id="req-5"))
assert forbidden_result.status == "DENIED"

slow_result = gateway.execute_request(ToolRequest(tool_id="calculator", arguments={"expression": "1+1"}, conversation_id="conv-6", request_id="req-6", timeout_seconds=0.01))
assert slow_result.status in {"TIMED_OUT", "FAILED", "EXECUTED"}

failure_result = gateway.execute_request(ToolRequest(tool_id="system.health", arguments={"force_fail": True}, conversation_id="conv-7", request_id="req-7"))
assert failure_result.status in {"FAILED", "INVALID_ARGUMENTS"}

malformed_result = gateway.execute_request(ToolRequest(tool_id="calculator", arguments={"expression": "2+2"}, conversation_id="conv-8", request_id="req-8"))
assert isinstance(malformed_result.output, dict)

path_traversal = gateway.execute_request(ToolRequest(tool_id="file.read", arguments={"path": "../secrets/.env"}, conversation_id="conv-9", request_id="req-9"))
assert path_traversal.status in {"DENIED", "INVALID_ARGUMENTS"}

unsafe_sql = gateway.execute_request(ToolRequest(tool_id="database.read", arguments={"operation": "execute_sql", "sql": "DROP TABLE users;"}, conversation_id="conv-10", request_id="req-10"))
assert unsafe_sql.status in {"DENIED", "INVALID_ARGUMENTS"}

assert len(gateway.audit_log) >= 1
record = gateway.audit_log[-1]
assert hasattr(record, "request_id") and hasattr(record, "tool_id")
assert "password" not in json.dumps(record.__dict__, default=str).lower()
assert "hidden reasoning" not in json.dumps(record.__dict__, default=str).lower()

# Live-chat tool decision boundary checks.
main_spec = importlib.util.spec_from_file_location(
    "shy_core_live_chat_tool_test",
    Path(__file__).resolve().parents[1] / "services" / "core" / "main.py",
)
main_module = importlib.util.module_from_spec(main_spec)
main_spec.loader.exec_module(main_module)

calc_decision = main_module.decide_chat_tool_request("What is 17% of 842?")
assert calc_decision == {
    "decision": "USE_TOOL",
    "tool_id": "calculator",
    "permission": "READ_ONLY",
    "validated_arguments": {"expression": "17% of 842"},
}

health_decision = main_module.decide_chat_tool_request("Is SHY's database connected?")
assert health_decision["tool_id"] == "system.health"
assert health_decision["permission"] == "READ_ONLY"

assert main_module.decide_chat_tool_request("Explain photosynthesis.") == {"decision": "NO_TOOL"}
assert main_module.decide_chat_tool_request("Read the SHY app config file") == {"decision": "NO_TOOL"}
assert main_module.decide_chat_tool_request("Read database tables") == {"decision": "USE_TOOL", "tool_id": "database.read", "permission": "READ_ONLY", "validated_arguments": {"operation": "tables"}}
assert main_module.decide_chat_tool_request("DROP TABLE users;") == {"decision": "NO_TOOL"}

print("tool intelligence tests: PASS")
