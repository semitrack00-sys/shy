import asyncio
import importlib.util
import sys
import types
import uuid
from pathlib import Path


root = Path(__file__).resolve().parents[1]
services = root / "services"


for name in ("httpx", "psycopg", "fastapi", "pydantic"):
    if name in sys.modules:
        continue
    try:
        __import__(name)
    except ModuleNotFoundError:
        if name == "httpx":
            module = types.ModuleType("httpx")

            class _HTTPError(Exception):
                pass

            class _AsyncClient:
                def __init__(self, *args, **kwargs):
                    pass

                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return False

                async def get(self, *args, **kwargs):
                    raise _HTTPError("stubbed httpx client")

                async def post(self, *args, **kwargs):
                    raise _HTTPError("stubbed httpx client")

            class _Client:
                def __init__(self, *args, **kwargs):
                    pass

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def get(self, *args, **kwargs):
                    raise _HTTPError("stubbed httpx client")

            module.HTTPError = _HTTPError
            module.AsyncClient = _AsyncClient
            module.Client = _Client
            sys.modules[name] = module
        elif name == "psycopg":
            module = types.ModuleType("psycopg")
            module.Error = type("PsycopgError", (Exception,), {})
            sys.modules[name] = module
        elif name == "fastapi":
            module = types.ModuleType("fastapi")

            class _HTTPException(Exception):
                def __init__(self, status_code, detail):
                    super().__init__(detail)
                    self.status_code = status_code
                    self.detail = detail

            class _FastAPI:
                def __init__(self, *args, **kwargs):
                    pass

                def on_event(self, *args, **kwargs):
                    def decorator(func):
                        return func

                    return decorator

                def get(self, *args, **kwargs):
                    def decorator(func):
                        return func

                    return decorator

                def post(self, *args, **kwargs):
                    def decorator(func):
                        return func

                    return decorator

            module.FastAPI = _FastAPI
            module.HTTPException = _HTTPException
            sys.modules[name] = module
        elif name == "pydantic":
            module = types.ModuleType("pydantic")

            class _BaseModel:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            module.BaseModel = _BaseModel
            sys.modules[name] = module


sys.path.insert(0, str(services))
sys.path.insert(0, str(services / "core"))

for package_name, package_path in (
    ("model_router", services / "model-router" / "app"),
    ("tools", services / "tools"),
    ("agent_runtime", services / "agent-runtime"),
    ("research", services / "research"),
):
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package


for module_name, module_path in (
    ("model_router.router", services / "model-router" / "app" / "router.py"),
    ("tools.gateway", services / "tools" / "gateway.py"),
    ("tools.contracts", services / "tools" / "contracts.py"),
    ("agent_runtime.runtime", services / "agent-runtime" / "runtime.py"),
    ("research.web_search", services / "research" / "web_search.py"),
    ("research.tavily", services / "research" / "tavily.py"),
    ("memory", services / "core" / "memory.py"),
):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


main_spec = importlib.util.spec_from_file_location("shy_core_chat_v013", services / "core" / "main.py")
main = importlib.util.module_from_spec(main_spec)
main_spec.loader.exec_module(main)


class FakeRoute:
    model = "qwen3.5:4b"
    provider = "ollama-local"
    task_type = "general"
    reason = "LOCAL_SUFFICIENT"


conversation_id = uuid.UUID("00000000-0000-0000-0000-000000000123")


main.create_conversation = lambda: conversation_id
main.conversation_exists = lambda cid: True
main._load_memory_history_for_message = lambda message, cid: ([], False)
main.save_message = lambda **kwargs: None
main.router.route = lambda message, privacy_requirement=None: FakeRoute()


async def _fake_generate_intelligence_response(message, history, route, generation_options=None):
    return "bounded response"


async def _fake_verifier(message, response_text):
    return response_text + " [verified]"


main.generate_intelligence_response = _fake_generate_intelligence_response
main._run_bounded_verification = _fake_verifier


verify_response = asyncio.run(
    main.chat(
        main.ChatRequest(
            message="Design a fault-tolerant payment processing architecture and explain the major tradeoffs.",
        )
    )
)

assert verify_response["status"] == "RESPOND"
assert verify_response["adaptive_mode"] == "verify"
assert verify_response["tool_decision"] == {"decision": "NO_TOOL"}
assert verify_response["verifier_invoked"] is True
assert verify_response["research_invoked"] is False
assert verify_response["hidden_reasoning_exposed"] is False
print("chat verify mode: PASS")


approval_gateway = main.ToolGateway(registry=main.tool_gateway.registry.__class__())
contracts = sys.modules["tools.contracts"]
approval_gateway.register_tool(
    contracts.ToolDefinition(
        tool_id="approval.tool",
        name="approval.tool",
        description="Synthetic approval test tool.",
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        permission_level=contracts.PermissionLevel.APPROVAL_REQUIRED,
        timeout_seconds=2.0,
    ),
    lambda: {"ok": True},
)
main.tool_gateway = approval_gateway
main.decide_chat_tool_request = lambda message: {
    "decision": "USE_TOOL",
    "tool_id": "approval.tool",
    "permission": "APPROVAL_REQUIRED",
    "validated_arguments": {},
}

approval_response = asyncio.run(
    main.chat(
        main.ChatRequest(
            message="Trigger approval path",
        )
    )
)

assert approval_response["status"] == "AWAITING_APPROVAL"
assert approval_response["approval_required"] is True
assert approval_response["tool_selected"] == "approval.tool"
assert approval_response["execution_status"] == "AWAITING_APPROVAL"
assert approval_response["adaptive_mode"] == "tool"
print("chat approval state: PASS")

print("v0.13 chat integration tests: PASS")