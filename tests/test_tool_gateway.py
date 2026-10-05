import importlib.util
from pathlib import Path


gateway_path = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "tools"
    / "gateway.py"
)

spec = importlib.util.spec_from_file_location(
    "shy_gateway",
    gateway_path,
)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

gateway = module.ToolGateway()

execution_count = {
    "health": 0,
    "approval": 0,
}


def health_tool():
    execution_count["health"] += 1
    return {"status": "healthy"}


def approval_tool(recipient, message):
    execution_count["approval"] += 1
    return {
        "sent": True,
        "recipient": recipient,
        "message": message,
    }


gateway.register("system.health", health_tool)
gateway.register(
    module.ToolDefinition(
        tool_id="approval.tool",
        name="approval.tool",
        description="Synthetic approval-gated tool for deterministic tests.",
        input_schema={
            "type": "object",
            "properties": {
                "recipient": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["recipient", "message"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "sent": {"type": "boolean"},
                "recipient": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["sent", "recipient", "message"],
        },
        permission_level=module.PermissionLevel.APPROVAL_REQUIRED,
        timeout_seconds=2.0,
    ),
    approval_tool,
)


safe = gateway.execute("system.health")

assert safe.status == "EXECUTED"
assert execution_count["health"] == 1
print("safe tool: EXECUTED")


arguments = {
    "recipient": "test@example.com",
    "message": "Hello",
}

blocked = gateway.execute(
    "approval.tool",
    arguments,
)

assert blocked.status == "AWAITING_APPROVAL"
assert execution_count["approval"] == 0
print("without approval: BLOCKED")


approval = gateway.approvals.create(
    "approval.tool",
    arguments,
)

approved = gateway.execute(
    "approval.tool",
    arguments,
    approval_token=approval.token,
)

assert approved.status == "EXECUTED"
assert execution_count["approval"] == 1
print("valid one-time approval: EXECUTED")


reused = gateway.execute(
    "approval.tool",
    arguments,
    approval_token=approval.token,
)

assert reused.status == "INVALID_APPROVAL"
assert execution_count["approval"] == 1
print("approval reuse: BLOCKED")


changed_arguments = {
    "recipient": "attacker@example.com",
    "message": "Hello",
}

approval2 = gateway.approvals.create(
    "approval.tool",
    arguments,
)

changed = gateway.execute(
    "approval.tool",
    changed_arguments,
    approval_token=approval2.token,
)

assert changed.status == "INVALID_APPROVAL"
assert execution_count["approval"] == 1
print("changed action: BLOCKED")


production_denied = gateway.execute(
    "message.send",
    arguments,
)

assert production_denied.status == "DENIED"
print("production message.send: DENIED")


unknown = gateway.execute(
    "unknown.dangerous.tool",
)

assert unknown.status == "DENIED"
print("unknown tool: DENIED")


try:
    gateway.execute(
        "approval.tool",
        arguments,
        human_approved=True,
    )
except TypeError:
    print("boolean approval bypass: NOT AVAILABLE")
else:
    raise AssertionError(
        "Boolean approval bypass still exists."
    )



failure_gateway = module.ToolGateway()


def failing_search_tool(query, max_results=5):
    raise RuntimeError("simulated provider failure")


failure_gateway.register(
    "web.search",
    failing_search_tool,
)

failed = failure_gateway.execute(
    "web.search",
    {
        "query": "test",
        "max_results": 5,
    },
)

assert failed.status == "FAILED"
assert failed.output is None
assert failed.reason == "Tool execution failed."
print("failing tool: FAILED safely")

print("SHY secure Tool Gateway tests: PASS")
