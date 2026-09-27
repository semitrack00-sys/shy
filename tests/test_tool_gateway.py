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


gateway.register(
    "system.health",
    health_tool,
)

gateway.register(
    "message.send",
    message_tool,
)


safe = gateway.execute("system.health")

assert safe.status == "EXECUTED"
assert safe.output["status"] == "healthy"
assert execution_count["health"] == 1

print("safe tool:", safe.status)


blocked = gateway.execute(
    "message.send",
    {
        "recipient": "test@example.com",
        "message": "Hello",
    },
)

assert blocked.status == "AWAITING_APPROVAL"
assert execution_count["message"] == 0

print("unapproved side effect:", blocked.status)


approved = gateway.execute(
    "message.send",
    {
        "recipient": "test@example.com",
        "message": "Hello",
    },
    human_approved=True,
)

assert approved.status == "EXECUTED"
assert execution_count["message"] == 1

print("approved side effect:", approved.status)


unknown = gateway.execute(
    "unknown.dangerous.tool",
)

assert unknown.status == "DENIED"

print("unknown tool:", unknown.status)


try:
    gateway.register(
        "unknown.dangerous.tool",
        lambda: "should never register",
    )
except ValueError:
    print("unknown registration: BLOCKED")
else:
    raise AssertionError(
        "Unknown tool registration should have failed."
    )


print("SHY Tool Gateway tests: PASS")
