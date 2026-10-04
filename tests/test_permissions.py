import importlib.util
from pathlib import Path


policy_path = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "permissions"
    / "policy.py"
)

spec = importlib.util.spec_from_file_location(
    "shy_permissions",
    policy_path,
)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def check(tool_name, expected):
    result = module.evaluate_tool(tool_name)

    print(
        f"{tool_name}: "
        f"{result.decision.value} "
        f"[{result.risk.value}]"
    )

    assert result.decision == expected


check("system.health", module.Decision.ALLOW)
check("memory.read", module.Decision.ALLOW)
check("web.search", module.Decision.ALLOW)

check(
    "message.send",
    module.Decision.DENY,
)

check(
    "file.delete",
    module.Decision.DENY,
)

check(
    "production.deploy",
    module.Decision.DENY,
)

check(
    "money.spend",
    module.Decision.DENY,
)

check(
    "totally.unknown.tool",
    module.Decision.DENY,
)

print("SHY permission tests: PASS")
