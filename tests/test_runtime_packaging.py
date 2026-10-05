import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1]
model_router_app = root / "services" / "model-router" / "app"

required_files = [
    "contracts.py",
    "router.py",
    "registry.py",
    "selection.py",
    "orchestrator.py",
    "providers/base.py",
    "providers/fake.py",
    "providers/ollama.py",
]

for relative in required_files:
    path = model_router_app / relative
    assert path.exists(), f"missing required runtime file: {relative}"

contracts_spec = importlib.util.spec_from_file_location("shy_model_contracts", model_router_app / "contracts.py")
contracts_module = importlib.util.module_from_spec(contracts_spec)
contracts_spec.loader.exec_module(contracts_module)
assert hasattr(contracts_module, "ModelCapability")

router_spec = importlib.util.spec_from_file_location("shy_model_router", model_router_app / "router.py")
router_module = importlib.util.module_from_spec(router_spec)
router_spec.loader.exec_module(router_module)
assert hasattr(router_module, "ModelRouter")

print("runtime packaging validation: PASS")
