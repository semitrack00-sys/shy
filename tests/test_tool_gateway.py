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
    "message": 0,
}


def health_tool():
    execution_count["health"] += 1
    return {"status": "healthy"}


def message_tool(recipient, message):
    execution_count["message"] += 1
    return {
        "sent": True,
        "recipient": recipient,
        "message": message,
    }


gateway.register("system.health", health_tool)
gateway.register("message.send", message_tool)


safe = gateway.execute("system.health")

assert safe.status == "EXECUTED"
assert execution_count["health"] == 1
print("safe tool: EXECUTED")


arguments = {
    "recipient": "test@example.com",
    "message": "Hello",
}

blocked = gateway.execute(
    "message.send",
    arguments,
)

assert blocked.status == "AWAITING_APPROVAL"
assert execution_count["message"] == 0
print("without approval: BLOCKED")


approval = gateway.approvals.create(
    "message.send",
    arguments,
)

approved = gateway.execute(
    "message.send",
    arguments,
    approval_token=approval.token,
)

assert approved.status == "EXECUTED"
assert execution_count["message"] == 1
print("valid one-time approval: EXECUTED")


reused = gateway.execute(
    "message.send",
    arguments,
    approval_token=approval.token,
)

assert reused.status == "INVALID_APPROVAL"
assert execution_count["message"] == 1
print("approval reuse: BLOCKED")


changed_arguments = {
    "recipient": "attacker@example.com",
    "message": "Hello",
}

approval2 = gateway.approvals.create(
    "message.send",
    arguments,
)

changed = gateway.execute(
    "message.send",
    changed_arguments,
    approval_token=approval2.token,
)

assert changed.status == "INVALID_APPROVAL"
assert execution_count["message"] == 1
print("changed action: BLOCKED")


unknown = gateway.execute(
    "unknown.dangerous.tool",
)

assert unknown.status == "DENIED"
print("unknown tool: DENIED")


try:
    gateway.execute(
        "message.send",
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
