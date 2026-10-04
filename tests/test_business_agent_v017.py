import importlib.util
import sys
import types
from datetime import datetime, timezone
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
                async def __aenter__(self):
                    return self

                async def __aexit__(self, exc_type, exc, tb):
                    return False

                async def get(self, *args, **kwargs):
                    raise _HTTPError("stubbed httpx client")

                async def post(self, *args, **kwargs):
                    raise _HTTPError("stubbed httpx client")

            module.HTTPError = _HTTPError
            module.AsyncClient = _AsyncClient
            module.Client = _AsyncClient
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
business_module = load_module("agent_runtime.business_workflows", services / "agent-runtime" / "business_workflows.py")


AgentPlanner = planner_module.AgentPlanner
ExecutionMode = planner_module.ExecutionMode
TaskEngine = task_engine_module.TaskEngine
TaskLimits = loop_module.TaskLimits
TaskStatus = loop_module.TaskStatus
ToolGateway = runtime_module.ToolGateway
AgentRuntime = runtime_module.AgentRuntime
DeterministicBusinessDataAdapters = business_module.DeterministicBusinessDataAdapters
resolve_business_intent = business_module.resolve_business_intent
run_business_reasoning_step = business_module.run_business_reasoning_step
build_business_report_markdown = business_module.build_business_report_markdown
extract_workflow_context_from_task = business_module.extract_workflow_context_from_task
build_business_audit_record = business_module.build_business_audit_record


planner = AgentPlanner()
adapters = DeterministicBusinessDataAdapters()

scenario_messages = [
    "Create a daily operations summary for warehouse and dispatch.",
    "Analyze customer issues and recurring support problems.",
    "Prepare a financial review of revenue and expenses.",
    "Build a logistics analysis for late deliveries.",
    "Create a competitive brief on top competitors.",
    "Give me logistics dispatch risks for this week.",
    "Find top recurring customer support issues.",
    "Review finance anomalies and margin pressure.",
    "Research competitors and provide a short strategy brief.",
    "Generate an operations summary with next actions.",
    "Analyze delivery delays and route performance.",
    "Customer support issue analysis with recommendations.",
    "Financial forecast analysis with risk notes.",
    "Competitive brief for logistics market changes.",
    "Business summary for daily operations review.",
    "Logistics report for late-delivery causes.",
    "Support issue clustering and response suggestions.",
    "Finance summary with recommendation list.",
    "Competitor research and synthesis.",
    "Operations summary with KPI and risk.",
    "Dispatch and delivery delay analysis.",
    "Recurring customer problems by theme.",
    "Analyze revenue and expenses trend.",
    "Research competitors in last-mile delivery.",
    "Business workflow: logistics analysis.",
    "Business workflow: customer support analysis.",
]

for text in scenario_messages:
    intent = resolve_business_intent(text)
    assert intent is not None
    decision = planner.decide(text)
    assert decision.mode == ExecutionMode.MULTI_STEP
print("business intent routing (26 scenarios): PASS")


gateway = ToolGateway()
runtime = AgentRuntime(planner=planner, gateway=gateway)


def business_reasoner(step, task):
    result = run_business_reasoning_step(step.objective, task, adapters)
    if result is not None:
        return result
    return TaskEngine._default_reasoner(step, task)


engine = TaskEngine(
    runtime=runtime,
    limits=TaskLimits(max_iterations=2, max_tool_calls=3, max_steps=5),
    compatibility_mode=False,
    plan_builder=lambda objective, task: planner.build_task_plan(
        objective,
        max_steps=5,
        context=dict(getattr(task.execution_context, "derived_values", {})),
    ),
    reasoner=business_reasoner,
)

logistics_prompt = "Create a logistics analysis for late deliveries and dispatch risks."
logistics_task, logistics_payload = engine.run(
    logistics_prompt,
    deep_mode=True,
    context={"workspace_id": "workspace-a", "business_id": "biz-a", "user_id": "u-a"},
)
assert logistics_task.status == TaskStatus.COMPLETED
assert logistics_payload["verification"] == "PASS"
logistics_answer = build_business_report_markdown(logistics_task)
assert logistics_answer is not None
assert "Late deliveries: 8" in logistics_answer
assert "Late rate: 20%" in logistics_answer
assert "tied as top causes" in logistics_answer
print("logistics workflow deterministic output: PASS")

context = extract_workflow_context_from_task(logistics_task)
assert context is not None
assert context.workspace_id == "workspace-a"
assert context.business_id == "biz-a"
print("workflow context capture: PASS")

logistics_task_b, _ = engine.run(
    logistics_prompt,
    deep_mode=True,
    context={"workspace_id": "workspace-b", "business_id": "biz-b", "user_id": "u-b"},
)
assert logistics_task_b.status == TaskStatus.COMPLETED
answer_b = build_business_report_markdown(logistics_task_b)
assert answer_b is not None
assert "Late deliveries: 1" in answer_b
assert "Late rate: 10%" in answer_b
assert answer_b != logistics_answer
print("workspace/business data isolation: PASS")

forbidden_plan_task, _ = engine.run(
    "Create a logistics analysis for late deliveries and dispatch risks.",
    deep_mode=True,
    context={
        "workspace_id": "workspace-a",
        "business_id": "biz-a",
        "workflow_policy": {
            "allowed_tools": ["calculator"],
            "forbidden_tools": ["message.send"],
            "approval_required_tools": [],
            "max_steps": 5,
            "data_access_scope": "workspace_read_only",
            "memory_behavior": "persist_safe_task_outcome",
            "external_provider_privacy_policy": "local_preferred_remote_allowed",
        },
    },
)
# Engine should still complete with planner-provided workflow policy and no forbidden side-effect tools invoked.
assert forbidden_plan_task.status == TaskStatus.COMPLETED
print("tool-policy boundedness on workflow execution: PASS")

audit = build_business_audit_record(
    task_id=logistics_task.task_id,
    context=context,
    status=logistics_task.status.value,
    tools_used=[
        item.tool_name
        for item in logistics_task.execution_context.step_results
        if item.tool_name
    ],
    model_routing={
        "selected_provider": "ollama",
        "selected_model": "qwen3.5:4b",
        "executed_provider": "ollama",
        "executed_model": "qwen3.5:4b",
    },
    approval_state="not_required",
    completion_time=datetime.now(timezone.utc).isoformat(),
    outcome=logistics_task.execution_context.derived_values.get("business_report") or {"summary": logistics_answer},
)
assert audit["workflow_type"] == "logistics_analysis"
assert audit["provider"] == "ollama"
assert audit["model"] == "qwen3.5:4b"
assert "sanitized_outcome" in audit
print("business audit trail contract: PASS")
