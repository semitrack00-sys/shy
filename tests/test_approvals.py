import importlib.util
from pathlib import Path


approval_path = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "permissions"
    / "approvals.py"
)

spec = importlib.util.spec_from_file_location(
    "shy_approvals",
    approval_path,
)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

store = module.ApprovalStore()

arguments = {
    "recipient": "test@example.com",
    "message": "Hello",
}

approval = store.create(
    "message.send",
    arguments,
)

assert store.consume(
    approval.token,
    "message.send",
    arguments,
)

print("exact approved action: ALLOWED")

assert not store.consume(
    approval.token,
    "message.send",
    arguments,
)

print("token reuse: BLOCKED")


approval2 = store.create(
    "message.send",
    arguments,
)

assert not store.consume(
    approval2.token,
    "money.spend",
    arguments,
)

print("different tool: BLOCKED")


approval3 = store.create(
    "message.send",
    arguments,
)

changed_arguments = {
    "recipient": "other@example.com",
    "message": "Hello",
}

assert not store.consume(
    approval3.token,
    "message.send",
    changed_arguments,
)

print("changed arguments: BLOCKED")


approval4 = store.create(
    "message.send",
    arguments,
    ttl_seconds=-1,
)

assert not store.consume(
    approval4.token,
    "message.send",
    arguments,
)

print("expired approval: BLOCKED")

print("SHY approval security tests: PASS")
