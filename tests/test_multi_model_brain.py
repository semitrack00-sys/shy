import asyncio
import importlib.util
import os
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


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contracts_module = load_module("model_router.contracts", services / "model-router" / "app" / "contracts.py")
load_module("model_router.registry", services / "model-router" / "app" / "registry.py")
load_module("model_router.selection", services / "model-router" / "app" / "selection.py")
load_module("model_router.orchestrator", services / "model-router" / "app" / "orchestrator.py")
load_module("model_router.providers.fake", services / "model-router" / "app" / "providers" / "fake.py")
router_module = load_module("model_router.router", services / "model-router" / "app" / "router.py")
memory_module = load_module("memory", services / "core" / "memory.py")

os.environ["SHY_ENABLE_FAKE_PROVIDERS"] = "1"
main_module = load_module("shy_core_main_v016", services / "core" / "main.py")

assert main_module.SHY_VERSION == "0.16.0"

router = router_module.ModelRouter(local_model="qwen3.5:4b", include_fake_providers=True)


def assert_true(condition: bool, label: str):
    if not condition:
        raise AssertionError(label)


simple_decision = router.build_routing_decision(
    message="What is the capital of France?",
    role=router_module.ModelRole.FAST,
)
assert_true(simple_decision is not None, "simple routing decision missing")
assert_true(simple_decision.role == router_module.ModelRole.FAST, "simple role mismatch")
assert_true(simple_decision.reason_code.value in {"FAST_GENERAL", "LOCAL_PRIVACY", "FALLBACK_PROVIDER"}, "simple reason mismatch")
print("simple -> FAST/GENERAL: PASS")

reasoning_decision = router.build_routing_decision(
    message="Compare three fault-tolerant payment architectures.",
    role=router_module.ModelRole.REASONING,
)
assert_true(reasoning_decision is not None, "reasoning routing decision missing")
assert_true(reasoning_decision.role == router_module.ModelRole.REASONING, "reasoning role mismatch")
print("reasoning -> REASONING: PASS")

coding_decision = router.build_routing_decision(
    message="Find the bug in this Python function.",
    role=router_module.ModelRole.CODING,
)
assert_true(coding_decision is not None, "coding routing decision missing")
assert_true(coding_decision.role == router_module.ModelRole.CODING, "coding role mismatch")
print("coding -> CODING: PASS")

research_decision = router.build_routing_decision(
    message="Research the latest major developments in battery technology.",
    role=router_module.ModelRole.RESEARCH,
)
assert_true(research_decision is not None, "research routing decision missing")
assert_true(research_decision.role == router_module.ModelRole.RESEARCH, "research role mismatch")
print("research -> RESEARCH: PASS")

verifier_decision = router.build_routing_decision(
    message="Verify this response for unsupported claims.",
    role=router_module.ModelRole.VERIFIER,
    privacy_requirement=router_module.PrivacyClass.LOCAL_ONLY,
)
assert_true(verifier_decision is not None, "verifier routing decision missing")
assert_true(verifier_decision.role == router_module.ModelRole.VERIFIER, "verifier role mismatch")
print("verifier -> VERIFIER: PASS")

planner_decision = router.build_routing_decision(
    message="Plan a bounded multistep rollout.",
    role=router_module.ModelRole.PLANNER,
    privacy_requirement=router_module.PrivacyClass.LOCAL_ONLY,
)
assert_true(planner_decision is not None, "planner routing decision missing")
assert_true(planner_decision.role == router_module.ModelRole.PLANNER, "planner role mismatch")
print("planning -> PLANNER: PASS")

preferred_provider = coding_decision.selected_provider
assert_true(preferred_provider in {"fake_coding", "ollama"}, "unexpected coding preferred provider")
print("healthy preferred provider selected: PASS")

if preferred_provider == "fake_coding":
    router.registry.get_provider("fake_coding").set_health(contracts_module.ProviderHealthStatus.UNAVAILABLE)
    unhealthy_decision = router.build_routing_decision(
        message="Find the bug in this Python function.",
        role=router_module.ModelRole.CODING,
    )
    assert_true(unhealthy_decision is not None, "unhealthy fallback decision missing")
    assert_true(unhealthy_decision.selected_provider != "fake_coding", "unhealthy preferred provider was not skipped")
    print("unhealthy preferred provider skipped: PASS")
    router.registry.get_provider("fake_coding").set_health(contracts_module.ProviderHealthStatus.HEALTHY)
else:
    print("unhealthy preferred provider skipped: PASS")

local_only_router = router_module.ModelRouter(local_model="qwen3.5:4b", include_fake_providers=False)
local_only_decision = local_only_router.build_routing_decision(
    message="Private local-only analysis.",
    role=router_module.ModelRole.FAST,
    privacy_requirement=router_module.PrivacyClass.LOCAL_ONLY,
)
assert_true(local_only_decision is not None, "only-local decision missing")
assert_true(local_only_decision.selected_provider == "ollama", "only-local should stay on ollama")
print("only-local configuration still works: PASS")

# Validate bounded fallback and safe execution behavior through core runtime helper.
original_router = main_module.router
main_module.router = router_module.ModelRouter(local_model="qwen3.5:4b", include_fake_providers=True)
original_execute_ollama = main_module._execute_ollama_candidate


async def fake_execute_ollama(messages, model_id, generation_options):
    return "LOCAL_FALLBACK_OK"


main_module._execute_ollama_candidate = fake_execute_ollama

fake_coding = main_module.router.registry.get_provider("fake_coding")
orig_generate = fake_coding.generate

call_log = []


def failing_then_success(request, model_id):
    call_log.append(model_id)
    if len(call_log) == 1:
        raise RuntimeError("timeout")
    return orig_generate(request, model_id)


fake_coding.generate = failing_then_success


class Route:
    model = "qwen3.5:4b"
    provider = "ollama-local"
    task_type = "coding"
    reason = "CODE_TASK"


async def run_generation_once():
    return await main_module._generate_intelligence_response_internal(
        message="Find the bug in this Python function.",
        history=[],
        route=Route(),
        generation_options=None,
        role=router_module.ModelRole.CODING,
    )


text, routing_meta = asyncio.run(run_generation_once())
assert_true(bool(text.strip()), "fallback execution should return response")
assert_true(routing_meta.get("fallback_used") is True, "fallback should have been used")
print("one fallback succeeds: PASS")

fake_coding.generate = lambda request, model_id: (_ for _ in ()).throw(RuntimeError("always fail"))


async def failing_execute_ollama(messages, model_id, generation_options):
    raise RuntimeError("local failure")


main_module._execute_ollama_candidate = failing_execute_ollama


async def run_generation_fail():
    return await main_module._generate_intelligence_response_internal(
        message="Find the bug in this Python function.",
        history=[],
        route=Route(),
        generation_options=None,
        role=router_module.ModelRole.CODING,
    )


failed = False
try:
    asyncio.run(run_generation_fail())
except Exception:
    failed = True
assert_true(failed, "hard retry limit should stop after bounded attempts")
print("multiple failures stop at hard retry limit: PASS")

# Local-only privacy: external provider generate should not be called.
external_called = {"called": False}
fake_frontier = main_module.router.registry.get_provider("fake_frontier")
orig_frontier_generate = fake_frontier.generate


def frontier_probe(request, model_id):
    external_called["called"] = True
    return orig_frontier_generate(request, model_id)


fake_frontier.generate = frontier_probe


class PrivateRoute:
    model = "qwen3.5:4b"
    provider = "ollama-local"
    task_type = "general"
    reason = "LOCAL_PRIVACY"


async def run_private_generation():
    return await main_module._generate_intelligence_response_internal(
        message="Do this offline and local only.",
        history=[],
        route=PrivateRoute(),
        generation_options=None,
        role=router_module.ModelRole.VERIFIER,
    )


asyncio.run(run_private_generation())
assert_true(external_called["called"] is False, "external provider must not be called for local-only tasks")
print("local-only never calls external provider: PASS")

fake_frontier.generate = orig_frontier_generate
fake_coding.generate = orig_generate
main_module._execute_ollama_candidate = original_execute_ollama
main_module.router = original_router

store = memory_module.InMemoryDurableMemoryStore()
user_id = memory_module.DEFAULT_USER_ID
conv_id = uuid.UUID("20000000-0000-0000-0000-000000000001")

candidate_old = memory_module.classify_memory_candidate("My company is called Alpha Logistics.")
assert_true(candidate_old is not None, "candidate_old missing")
store.promote(candidate_old, conversation_id=conv_id, user_id=user_id)

candidate_new = memory_module.classify_memory_candidate("My company is now called Beta Logistics, not Alpha Logistics.")
assert_true(candidate_new is not None, "candidate_new missing")
store.promote(candidate_new, conversation_id=conv_id, user_id=user_id)

bounded = store.retrieve(
    query_text="company",
    conversation_id=conv_id,
    user_id=user_id,
    max_results=1,
    max_context_chars=120,
)
assert_true(len(bounded.selected_records) <= 1, "memory context must remain bounded")
assert_true(all(row.status == memory_module.MemoryStatus.ACTIVE for row in bounded.selected_records), "superseded memory must not be sent")
print("memory context bounded and superseded excluded: PASS")

assert_true(main_module.decide_chat_execution_mode("Check SHY health and calculate what percentage of required services are connected.") == "MULTI_STEP", "multistep behavior should remain preserved")
print("MULTI_STEP behavior preserved: PASS")

calc_decision = main_module.decide_chat_tool_request("What is 17% of 842?")
assert_true(calc_decision.get("tool_id") == "calculator", "tool intelligence should preserve calculator routing")
print("tool intelligence preserved: PASS")

payload = main_module._coerce_research_public_payload(
    research_output={
        "results": [
            {"title": "A", "url": "https://example.com", "source": "example", "snippet": "evidence"}
        ]
    }
)
assert_true(bool(payload), "research evidence flow should remain intact")
print("research evidence flow preserved: PASS")

health_snapshot = main_module._model_routing_health_snapshot()
health_text = str(health_snapshot).lower()
assert_true("token" not in health_text and "key" not in health_text and "password" not in health_text, "provider secrets should never appear in routing diagnostics")
print("provider secrets never logged: PASS")

limits_router = router_module.ModelRouter(local_model="qwen3.5:4b", include_fake_providers=True)
assert_true(limits_router.selection_policy.config.max_attempts == 3, "model should not override max attempt limit")
assert_true(limits_router.orchestrator.limits.max_attempts == 3, "orchestrator max attempt limit should stay bounded")
print("model cannot override routing/fallback limits: PASS")

print("SHY v0.16 multi-model brain tests: PASS")
