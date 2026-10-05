import asyncio
import importlib.util
import sys
import types
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


planner_module = load_module("agent_runtime.planner", services / "agent-runtime" / "planner.py")
loop_module = load_module("agent_runtime.loop_state", services / "agent-runtime" / "loop_state.py")
contracts_module = load_module("tools.contracts", services / "tools" / "contracts.py")
runtime_module = load_module("agent_runtime.runtime", services / "agent-runtime" / "runtime.py")
task_engine_module = load_module("agent_runtime.task_engine", services / "agent-runtime" / "task_engine.py")
load_module("research.web_search", services / "research" / "web_search.py")
load_module("research.tavily", services / "research" / "tavily.py")
load_module("memory", services / "core" / "memory.py")
task_persistence_module = load_module("task_persistence", services / "core" / "task_persistence.py")
main_module = load_module("shy_core_main_v014", services / "core" / "main.py")
assert tuple(int(part) for part in main_module.SHY_VERSION.split(".")) >= (0, 17, 0)


AgentPlanner = planner_module.AgentPlanner
ExecutionMode = planner_module.ExecutionMode
TaskEngine = task_engine_module.TaskEngine
TaskLimits = loop_module.TaskLimits
TaskStatus = loop_module.TaskStatus
ActionType = loop_module.ActionType
VerificationResult = loop_module.VerificationResult
VerificationOutcome = loop_module.VerificationOutcome
VerificationIssue = loop_module.VerificationIssue
ToolGateway = runtime_module.ToolGateway
AgentRuntime = runtime_module.AgentRuntime
ToolDefinition = contracts_module.ToolDefinition
PermissionLevel = contracts_module.PermissionLevel
AgentResult = runtime_module.AgentResult
STEP_LIMIT_REACHED = loop_module.STEP_LIMIT_REACHED
INVALID_PLAN = loop_module.INVALID_PLAN
VERIFICATION_FAILED = loop_module.VERIFICATION_FAILED
TOOL_DENIED = loop_module.TOOL_DENIED


planner = AgentPlanner()
assert planner.decide("Explain photosynthesis.").mode == ExecutionMode.DIRECT
print("DIRECT routing decision: PASS")

calc_decision = planner.decide("What is 17% of 842?")
assert calc_decision.mode == ExecutionMode.SINGLE_TOOL
assert calc_decision.tool_name == "calculator"
assert calc_decision.arguments == {"expression": "17% of 842"}
print("SINGLE_TOOL routing decision: PASS")

multi_prompt = "Check SHY health and calculate what percentage of its required services are connected."
multi_decision = planner.decide(multi_prompt)
assert multi_decision.mode == ExecutionMode.MULTI_STEP
multi_plan = planner.build_task_plan(multi_prompt, max_steps=99)
assert multi_plan is not None
assert multi_plan["maximum_step_count"] == 8
assert len(multi_plan["steps"]) == 4
print("MULTI_STEP routing decision: PASS")


gateway = ToolGateway()
gateway.register(
    "system.health",
    lambda: {
        "status": "ok",
        "application_healthy": True,
        "ollama_connected": True,
        "database_connected": True,
        "local_model_available": True,
        "local_model": "qwen3.5:4b",
    },
)
runtime = AgentRuntime(planner=planner, gateway=gateway)
engine = TaskEngine(
    runtime=runtime,
    limits=TaskLimits(max_iterations=3, max_tool_calls=3, max_steps=5),
    compatibility_mode=False,
    plan_builder=lambda objective, _task: planner.build_task_plan(objective, max_steps=5),
)
completed_task, completed_payload = engine.run(multi_prompt, deep_mode=True)
assert completed_task.status == TaskStatus.COMPLETED
assert [step.status.value for step in completed_task.plan_steps] == ["EXECUTED", "EXECUTED", "EXECUTED", "EXECUTED"]
assert completed_task.tool_call_count == 2
assert completed_payload["verification"] == "PASS"
assert "100" in completed_task.plan_steps[-1].result_summary
print("ordered multistep execution: PASS")

capped_limits = TaskLimits(max_iterations=2, max_tool_calls=1, max_steps=99)
assert capped_limits.max_steps == 8
step_limit_engine = TaskEngine(
    runtime=runtime,
    limits=capped_limits,
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: {
        "goal": "Too many steps",
        "maximum_step_count": 999,
        "completion_criteria": "N/A",
        "failure_policy": "Stop",
        "steps": [
            {
                "step_id": index,
                "action_type": "REASON",
                "objective": f"Reason step {index}",
            }
            for index in range(1, 10)
        ],
    },
)
step_limit_task, _ = step_limit_engine.run("too many", deep_mode=True)
assert step_limit_task.status == TaskStatus.FAILED
assert step_limit_task.failure_reason == STEP_LIMIT_REACHED
print("hard max-step enforcement: PASS")

retry_counter = {"count": 0}


def flaky_reasoner(step, _task):
    retry_counter["count"] += 1
    return {
        "status": "FAILED",
        "summary": "",
        "error_code": "TEMPORARY_REASONING_ERROR",
        "recoverable": True,
    }


retry_engine = TaskEngine(
    runtime=runtime,
    limits=TaskLimits(max_iterations=3, max_tool_calls=1, max_steps=3),
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "Retry once only",
        }
    ],
    reasoner=flaky_reasoner,
)
retry_task, _ = retry_engine.run("retry", deep_mode=True)
assert retry_task.status == TaskStatus.FAILED
assert retry_counter["count"] == 2
assert retry_task.plan_steps[0].retry_count == 1
print("bounded retry and no infinite loop: PASS")

approval_gateway = ToolGateway()
approval_gateway.register_tool(
    ToolDefinition(
        tool_id="approval.tool",
        name="approval.tool",
        description="Synthetic approval-gated tool.",
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
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        permission_level=PermissionLevel.APPROVAL_REQUIRED,
        timeout_seconds=2.0,
    ),
    lambda recipient, message: {"ok": True},
)
approval_runtime = AgentRuntime(planner=planner, gateway=approval_gateway)
approval_engine = TaskEngine(
    runtime=approval_runtime,
    limits=TaskLimits(max_iterations=3, max_tool_calls=2, max_steps=3),
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "Send a message with approval",
            "tool_name": "approval.tool",
            "tool_args": {"recipient": "a@example.com", "message": "hello"},
        }
    ],
)
paused_task, _ = approval_engine.run("approval", deep_mode=True)
assert paused_task.status == TaskStatus.AWAITING_APPROVAL
assert paused_task.execution_context.awaiting_tool_name == "approval.tool"
matching_approval = approval_gateway.approvals.create(
    "approval.tool",
    {"recipient": "a@example.com", "message": "hello"},
    scope=f"{paused_task.task_id}:1",
)
resumed_task, _ = approval_engine.resume_task(paused_task, matching_approval.token)
assert resumed_task.status == TaskStatus.COMPLETED
print("approval pause and exact resume: PASS")

paused_task_2, _ = approval_engine.run("approval-again", deep_mode=True)
wrong_approval = approval_gateway.approvals.create(
    "approval.tool",
    {"recipient": "wrong@example.com", "message": "hello"},
    scope=f"{paused_task_2.task_id}:1",
)
failed_resume_task, _ = approval_engine.resume_task(paused_task_2, wrong_approval.token)
assert failed_resume_task.status == TaskStatus.FAILED
print("approval resume exact-step enforcement: PASS")

blocked_runtime = AgentRuntime(planner=planner, gateway=ToolGateway())
blocked_engine = TaskEngine(
    runtime=blocked_runtime,
    limits=TaskLimits(max_iterations=2, max_tool_calls=1, max_steps=2),
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "Delete a file",
            "tool_name": "file.delete",
            "tool_args": {"path": "services/core/main.py"},
        }
    ],
)
blocked_task, _ = blocked_engine.run("forbidden", deep_mode=True)
assert blocked_task.status == TaskStatus.BLOCKED
assert blocked_task.failure_reason == TOOL_DENIED
print("forbidden tool stop: PASS")


class MalformedRuntime:
    def execute_tool_step(self, *args, **kwargs):
        return AgentResult(
            status="TOOL_RESULT",
            reason="malformed",
            tool_name="system.health",
            tool_status="EXECUTED",
            output="not-a-dict",
        )


malformed_engine = TaskEngine(
    runtime=MalformedRuntime(),
    limits=TaskLimits(max_iterations=2, max_tool_calls=1, max_steps=2),
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "health",
            "tool_name": "system.health",
            "tool_args": {},
        }
    ],
)
malformed_task, _ = malformed_engine.run("malformed", deep_mode=True)
assert malformed_task.status == TaskStatus.FAILED
assert malformed_task.plan_steps[0].error == "MALFORMED_TOOL_RESULT"
print("malformed tool result stop: PASS")


class InjectionRuntime:
    def execute_tool_step(self, *args, **kwargs):
        return AgentResult(
            status="TOOL_RESULT",
            reason="tool injection",
            tool_name="file.delete",
            tool_status="EXECUTED",
            output={"ok": True},
        )


injection_engine = TaskEngine(
    runtime=InjectionRuntime(),
    limits=TaskLimits(max_iterations=2, max_tool_calls=1, max_steps=2),
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "health",
            "tool_name": "system.health",
            "tool_args": {},
        }
    ],
)
injection_task, _ = injection_engine.run("injection", deep_mode=True)
assert injection_task.status == TaskStatus.FAILED
assert injection_task.plan_steps[0].error == "UNSUPPORTED_OUTPUT"
print("tool injection attempt rejected: PASS")

duplicate_engine = TaskEngine(
    runtime=runtime,
    limits=TaskLimits(max_iterations=2, max_tool_calls=1, max_steps=5),
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "duplicate",
        },
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "duplicate",
        },
    ],
)
duplicate_task, _ = duplicate_engine.run("duplicate", deep_mode=True)
assert duplicate_task.status == TaskStatus.FAILED
assert duplicate_task.failure_reason == INVALID_PLAN
print("duplicate step prevention: PASS")

cancelled_task = retry_engine.create_task(
    "cancel me",
    verification_required=True,
    execution_mode="MULTI_STEP",
)
retry_engine.cancel_task(cancelled_task)
assert cancelled_task.status == TaskStatus.CANCELLED
print("cancellation: PASS")

verify_fail_engine = TaskEngine(
    runtime=runtime,
    limits=TaskLimits(max_iterations=2, max_tool_calls=1, max_steps=2),
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "Generate summary",
        }
    ],
    reasoner=lambda _step, _task: {
        "status": "EXECUTED",
        "summary": "summary",
        "evidence": False,
    },
    verifier=lambda _task: VerificationResult(
        outcome=VerificationOutcome.FAIL,
        issues=(VerificationIssue.INCOMPLETE_RESULT,),
        summary="verification failed",
    ),
)
verify_fail_task, _ = verify_fail_engine.run("verify fail", deep_mode=True)
assert verify_fail_task.status == TaskStatus.FAILED
assert verify_fail_task.failure_reason == VERIFICATION_FAILED
print("verifier completion gate: PASS")

for forbidden in ("chain_of_thought", "hidden_reasoning", "scratchpad"):
    assert forbidden not in vars(completed_task)
    for plan_step in completed_task.plan_steps:
        assert forbidden not in vars(plan_step)
    for step_result in completed_task.execution_context.step_results:
        assert forbidden not in vars(step_result)
print("hidden reasoning never exposed: PASS")


class FakeRoute:
    def __init__(self, task_type: str):
        self.model = "qwen3.5:4b"
        self.provider = "ollama-local"
        self.task_type = task_type
        self.reason = "LOCAL_SUFFICIENT"


main_module.create_conversation = lambda: Path("/tmp") or None
main_module.conversation_exists = lambda _cid: True
main_module._load_memory_history_for_message = lambda message, cid: ([], False)
main_module.save_message = lambda **kwargs: None
main_module.agent_runtime = runtime
main_module.chat_task_engine = TaskEngine(
    runtime=runtime,
    limits=TaskLimits(max_iterations=3, max_tool_calls=3, max_steps=5),
    compatibility_mode=False,
    plan_builder=lambda objective, _task: planner.build_task_plan(objective, max_steps=5),
)
main_module.tool_gateway = gateway
main_module.chat_task_store = {}


async def fake_generate_intelligence_response(message, history, route, generation_options=None):
    return "simple direct answer"


async def fake_generate_research_response(message, research_output=None, research_result=None):
    return "grounded research answer [1]"


class FakeResearchResult:
    status = "COMPLETE"
    evidence = [{"title": "Battery note", "url": "https://example.com", "source": "example.com", "snippet": "Battery update"}]

    def to_public_dict(self):
        return {
            "provider": "fake-research",
            "evidence": self.evidence,
            "results": self.evidence,
        }


async def fake_run_research_pipeline(message):
    return FakeResearchResult()


main_module.generate_intelligence_response = fake_generate_intelligence_response
main_module.generate_research_response = fake_generate_research_response
main_module.run_research_pipeline = fake_run_research_pipeline
main_module.chat_task_repository = task_persistence_module.InMemoryTaskRepository()
main_module.router.route = lambda message, privacy_requirement=None: (
    FakeRoute("research")
    if message.lower().startswith("research ")
    else FakeRoute("reasoning")
)

calc_response = asyncio.run(
    main_module.chat(main_module.ChatRequest(message="What is 17% of 842?"))
)
assert calc_response["adaptive_mode"] == "tool"
assert calc_response["tool_selected"] == "calculator"
assert calc_response["message"] == "The result is 143.14."
print("v0.13 calculator behavior preserved: PASS")

health_response = asyncio.run(
    main_module.chat(main_module.ChatRequest(message="Is SHY's database connected?"))
)
assert health_response["adaptive_mode"] == "tool"
assert health_response["tool_selected"] == "system.health"
assert "database is connected" in health_response["message"].lower()
print("v0.13 system.health behavior preserved: PASS")

direct_response = asyncio.run(
    main_module.chat(main_module.ChatRequest(message="Explain photosynthesis."))
)
assert direct_response["adaptive_mode"] == "direct"
assert direct_response["verifier_invoked"] is False
print("DIRECT chat path preserved: PASS")

multistep_response = asyncio.run(
    main_module.chat(main_module.ChatRequest(message=multi_prompt))
)
assert multistep_response["adaptive_mode"] == "MULTI_STEP"
assert multistep_response["verifier_invoked"] is True
assert "100" in multistep_response["message"]
print("MULTI_STEP chat path: PASS")

research_response = asyncio.run(
    main_module.chat(main_module.ChatRequest(message="Research the latest major developments in battery technology."))
)
assert research_response["adaptive_mode"] == "research"
assert research_response["research_invoked"] is True
assert "[1]" in research_response["message"]
print("v0.12 research behavior preserved: PASS")


approval_runtime_for_chat = AgentRuntime(planner=planner, gateway=approval_gateway)
main_module.agent_runtime = approval_runtime_for_chat
main_module.chat_task_engine = TaskEngine(
    runtime=approval_runtime_for_chat,
    limits=TaskLimits(max_iterations=3, max_tool_calls=2, max_steps=3),
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "Send a message with approval",
            "tool_name": "approval.tool",
            "tool_args": {"recipient": "persist@example.com", "message": "hello"},
        }
    ],
)
main_module.chat_task_repository = task_persistence_module.InMemoryTaskRepository()
main_module.router.route = lambda _message, privacy_requirement=None: FakeRoute("reasoning")
conversation_id = "00000000-0000-0000-0000-000000000321"

awaiting_response = asyncio.run(
    main_module._handle_multistep_chat_request(
        main_module.ChatRequest(message="approval workflow"),
        conversation_id,
        FakeRoute("reasoning"),
    )
)
assert awaiting_response["status"] == "AWAITING_APPROVAL"
task_id = awaiting_response["task_id"]
assert task_id

approval_token = approval_gateway.approvals.create(
    "approval.tool",
    {"recipient": "persist@example.com", "message": "hello"},
    scope=f"{task_id}:1",
).token
assert approval_token

# Simulate restart by constructing fresh runtime/engine while reusing persisted repository state.
main_module.chat_task_engine = TaskEngine(
    runtime=approval_runtime_for_chat,
    limits=TaskLimits(max_iterations=3, max_tool_calls=2, max_steps=3),
    compatibility_mode=False,
    plan_builder=lambda _objective, _task: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "Send a message with approval",
            "tool_name": "approval.tool",
            "tool_args": {"recipient": "persist@example.com", "message": "hello"},
        }
    ],
)

resumed_response = asyncio.run(
    main_module._handle_multistep_chat_request(
        main_module.ChatRequest(
            message="resume",
            task_id=task_id,
            approval_token=approval_token,
            pending_step_id=1,
        ),
        conversation_id,
        FakeRoute("reasoning"),
    )
)
assert resumed_response["status"] == "RESPOND"
assert resumed_response["task_status"] == "COMPLETED"

persisted_completed = main_module.chat_task_repository.load_task(task_id)
assert persisted_completed is not None
assert persisted_completed.task.status == TaskStatus.COMPLETED

try:
    asyncio.run(
        main_module._handle_multistep_chat_request(
            main_module.ChatRequest(
                message="resume again",
                task_id=task_id,
                approval_token=approval_token,
                pending_step_id=1,
            ),
            conversation_id,
            FakeRoute("reasoning"),
        )
    )
    raise AssertionError("completed task should not be resumable")
except main_module.HTTPException as exc:
    assert exc.status_code == 409

completed_again = main_module.chat_task_repository.load_task(task_id)
assert completed_again is not None
assert completed_again.task.status == TaskStatus.COMPLETED
assert len(completed_again.task.execution_context.step_results) == 1

stale_repo = task_persistence_module.InMemoryTaskRepository()
main_module.chat_task_repository = stale_repo
stale_task_response = asyncio.run(
    main_module._handle_multistep_chat_request(
        main_module.ChatRequest(message="approval workflow stale revision"),
        conversation_id,
        FakeRoute("reasoning"),
    )
)
stale_task_id = stale_task_response["task_id"]
stale_snapshot_a = stale_repo.load_task(stale_task_id)
stale_snapshot_b = stale_repo.load_task(stale_task_id)
assert stale_snapshot_a is not None
assert stale_snapshot_b is not None
expected_revision = stale_snapshot_a.revision
baseline_step_results = len(stale_snapshot_a.task.execution_context.step_results)

task_copy_a = stale_snapshot_a.task
task_copy_a.failure_reason = "UPDATED_BY_A"
task_copy_a.execution_context.failure_policy = "Stop on stale test"
advanced_revision = stale_repo.save_task(
    task=task_copy_a,
    conversation_id=stale_snapshot_a.conversation_id,
    execution_mode=stale_snapshot_a.execution_mode,
    expected_revision=expected_revision,
)
assert advanced_revision == expected_revision + 1

task_copy_b = stale_snapshot_b.task
task_copy_b.failure_reason = "STALE_COPY_B"
try:
    stale_repo.save_task(
        task=task_copy_b,
        conversation_id=stale_snapshot_b.conversation_id,
        execution_mode=stale_snapshot_b.execution_mode,
        expected_revision=expected_revision,
    )
    raise AssertionError("stale revision save must be rejected")
except task_persistence_module.StaleTaskVersionError:
    pass

stale_final = stale_repo.load_task(stale_task_id)
assert stale_final is not None
assert stale_final.revision == advanced_revision
assert stale_final.task.failure_reason == "UPDATED_BY_A"
assert stale_final.task.failure_reason != "STALE_COPY_B"
assert len(stale_final.task.execution_context.step_results) == baseline_step_results


class AlwaysStaleCreateRepository(task_persistence_module.InMemoryTaskRepository):
    def create_task(self, task, conversation_id, execution_mode):
        raise task_persistence_module.StaleTaskVersionError("forced stale create")


main_module.chat_task_repository = AlwaysStaleCreateRepository()
try:
    asyncio.run(
        main_module._handle_multistep_chat_request(
            main_module.ChatRequest(message="force stale api mapping"),
            conversation_id,
            FakeRoute("reasoning"),
        )
    )
    raise AssertionError("stale create should map to HTTP 409")
except main_module.HTTPException as exc:
    assert exc.status_code == 409

main_module.chat_task_repository = task_persistence_module.InMemoryTaskRepository()

cancel_task_response = asyncio.run(
    main_module._handle_multistep_chat_request(
        main_module.ChatRequest(message="approval workflow 2"),
        conversation_id,
        FakeRoute("reasoning"),
    )
)
cancel_task_id = cancel_task_response["task_id"]

cancelled_response = asyncio.run(
    main_module._handle_multistep_chat_request(
        main_module.ChatRequest(message="cancel it", task_id=cancel_task_id, cancel_task=True),
        conversation_id,
        FakeRoute("reasoning"),
    )
)
assert cancelled_response["status"] == "CANCELLED"
persisted_cancelled = main_module.chat_task_repository.load_task(cancel_task_id)
assert persisted_cancelled is not None
assert persisted_cancelled.task.status == TaskStatus.CANCELLED

try:
    asyncio.run(
        main_module._handle_multistep_chat_request(
            main_module.ChatRequest(
                message="bad task",
                task_id="00000000-0000-0000-0000-000000000000",
                approval_token="nope",
                pending_step_id=1,
            ),
            conversation_id,
            FakeRoute("reasoning"),
        )
    )
    raise AssertionError("unknown task id should fail")
except main_module.HTTPException as exc:
    assert exc.status_code == 404

main_module.chat_task_repository.corrupt_task_payload(cancel_task_id, "not-json")
try:
    asyncio.run(
        main_module._handle_multistep_chat_request(
            main_module.ChatRequest(
                message="resume malformed",
                task_id=cancel_task_id,
                approval_token="x",
                pending_step_id=1,
            ),
            conversation_id,
            FakeRoute("reasoning"),
        )
    )
    raise AssertionError("malformed persisted state should fail safely")
except main_module.HTTPException as exc:
    assert exc.status_code == 409

payload = main_module.chat_task_repository.debug_raw_task_payload(cancel_task_id)
assert payload is not None
payload_text = str(payload).lower()
assert "approval_token" not in payload_text
assert approval_token.lower() not in payload_text

concurrency_repo = task_persistence_module.InMemoryTaskRepository()
concurrency_repo.ensure_schema()
main_module.chat_task_repository = concurrency_repo
concurrency_task_response = asyncio.run(
    main_module._handle_multistep_chat_request(
        main_module.ChatRequest(message="approval workflow 3"),
        conversation_id,
        FakeRoute("reasoning"),
    )
)
concurrency_task_id = concurrency_task_response["task_id"]
with concurrency_repo.task_lock(concurrency_task_id):
    try:
        asyncio.run(
            main_module._handle_multistep_chat_request(
                main_module.ChatRequest(
                    message="resume",
                    task_id=concurrency_task_id,
                    approval_token="blocked-token",
                    pending_step_id=1,
                ),
                conversation_id,
                FakeRoute("reasoning"),
            )
        )
        raise AssertionError("concurrent resume should be blocked by task lock")
    except main_module.HTTPException as exc:
        assert exc.status_code == 409

print("durable task persistence + restart + safety checks: PASS")

print("SHY v0.14 multistep agent tests: PASS")
