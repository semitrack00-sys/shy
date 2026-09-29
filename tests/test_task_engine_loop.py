import importlib.util
from pathlib import Path
from types import SimpleNamespace


root = Path(__file__).resolve().parents[1]
loop_state_path = root / "services" / "agent-runtime" / "loop_state.py"
task_engine_path = root / "services" / "agent-runtime" / "task_engine.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loop_module = load_module("shy_loop_state_test", loop_state_path)
engine_module = load_module("shy_task_engine_test", task_engine_path)

TaskEngineState = loop_module.TaskEngineState
TaskStatus = loop_module.TaskStatus
TaskLimits = loop_module.TaskLimits
TaskState = loop_module.TaskState
ActionType = loop_module.ActionType
PlanStep = loop_module.PlanStep
PlanStepStatus = loop_module.PlanStepStatus
VerificationResult = loop_module.VerificationResult
VerificationOutcome = loop_module.VerificationOutcome
VerificationIssue = loop_module.VerificationIssue
ITERATION_LIMIT_REACHED = loop_module.ITERATION_LIMIT_REACHED
STEP_LIMIT_REACHED = loop_module.STEP_LIMIT_REACHED
TOOL_CALL_LIMIT_REACHED = loop_module.TOOL_CALL_LIMIT_REACHED
INVALID_PLAN = loop_module.INVALID_PLAN
APPROVAL_REQUIRED = loop_module.APPROVAL_REQUIRED
TOOL_DENIED = loop_module.TOOL_DENIED
VERIFICATION_FAILED = loop_module.VERIFICATION_FAILED
TaskEngine = engine_module.TaskEngine


class FakeRuntime:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def run(self, message):
        self.calls += 1
        return self.result


initial = TaskState.create("Draft a response")
assert initial.state == TaskEngineState.UNDERSTAND
assert initial.status == TaskStatus.RUNNING
print("initial state: PASS")


transitions = TaskState.create("Check transitions")
transitions.transition_to(TaskEngineState.PLAN)
transitions.transition_to(TaskEngineState.EXECUTE)
transitions.transition_to(TaskEngineState.OBSERVE)
transitions.transition_to(TaskEngineState.FINISH)
assert transitions.status == TaskStatus.FINISHED
print("valid transitions: PASS")


invalid = TaskState.create("Reject invalid transition")
try:
    invalid.transition_to(TaskEngineState.FINISH)
    raise AssertionError("Invalid transition was not rejected.")
except ValueError:
    pass
print("invalid transition rejection: PASS")


iteration_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=1, max_steps=10, max_tool_calls=1),
)
iteration_task = iteration_engine.create_task("Iteration limit")
assert iteration_engine.advance(iteration_task, TaskEngineState.PLAN, "understand") is True
assert iteration_engine.advance(iteration_task, TaskEngineState.EXECUTE, "plan") is True
assert iteration_engine.advance(iteration_task, TaskEngineState.OBSERVE, "execute") is True
assert iteration_engine.advance(iteration_task, TaskEngineState.REVISE, "observe") is True
assert iteration_engine.advance(iteration_task, TaskEngineState.PLAN, "revise") is False
assert iteration_task.status == TaskStatus.FAILED
assert iteration_task.failure_reason == ITERATION_LIMIT_REACHED
print("max iterations: PASS")


step_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=3, max_steps=2, max_tool_calls=1),
)
step_task = step_engine.create_task("Step limit")
assert step_engine.advance(step_task, TaskEngineState.PLAN, "understand") is True
assert step_engine.advance(step_task, TaskEngineState.EXECUTE, "plan") is True
assert step_engine.advance(step_task, TaskEngineState.OBSERVE, "execute") is False
assert step_task.status == TaskStatus.FAILED
assert step_task.failure_reason == STEP_LIMIT_REACHED
print("max steps: PASS")


tool_runtime = FakeRuntime(SimpleNamespace(status="TOOL_RESULT", tool_name="system.health"))
tool_engine = TaskEngine(
    runtime=tool_runtime,
    limits=TaskLimits(max_iterations=2, max_steps=8, max_tool_calls=0),
)
tool_task, tool_result = tool_engine.run("Use system health")
assert tool_result.status == "TOOL_RESULT"
assert tool_task.status == TaskStatus.FAILED
assert tool_task.failure_reason == TOOL_CALL_LIMIT_REACHED
print("max tool calls: PASS")


respond_runtime = FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None))
compat_engine = TaskEngine(
    runtime=respond_runtime,
    limits=TaskLimits(max_iterations=2, max_steps=8, max_tool_calls=1),
    compatibility_mode=True,
)
finished_task, runtime_result = compat_engine.run("Hello SHY")
assert runtime_result.status == "RESPOND"
assert finished_task.status == TaskStatus.FINISHED
assert finished_task.state == TaskEngineState.FINISH
assert respond_runtime.calls == 1
print("successful finish: PASS")


failure_engine = TaskEngine(
    runtime=None,
    limits=TaskLimits(max_iterations=2, max_steps=8, max_tool_calls=1),
)
failed_task, none_result = failure_engine.run("Run without runtime")
assert none_result is None
assert failed_task.status == TaskStatus.FAILED
print("controlled failure: PASS")


assert all(not hasattr(step, "reasoning") for step in finished_task.steps)
assert all(not hasattr(step, "chain_of_thought") for step in finished_task.steps)
print("structured artifacts only: PASS")


def deep_plan_builder(_objective, _task):
    return [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "Gather constraints",
        },
        {
            "step_id": 2,
            "action_type": "REASON",
            "objective": "Produce staged plan",
        },
    ]


def deep_reasoner(step, _task):
    return {
        "status": "EXECUTED",
        "summary": f"done:{step.step_id}",
        "evidence": False,
    }


deep_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=5, max_steps=8, max_tool_calls=2),
    plan_builder=deep_plan_builder,
    reasoner=deep_reasoner,
)
deep_task, deep_payload = deep_engine.run(
    "Compare constraints and create a plan",
    deep_mode=True,
)
assert deep_task.status == TaskStatus.FINISHED
assert deep_task.state == TaskEngineState.FINISH
assert deep_payload["verification"] == "PASS"
print("successful multi-step deep flow: PASS")


revision_attempts = {"count": 0}


def revising_reasoner(step, _task):
    revision_attempts["count"] += 1

    if revision_attempts["count"] == 1:
        return {
            "status": "FAILED",
            "summary": "",
            "error_code": "TEMPORARY_REASONING_ERROR",
            "recoverable": True,
        }

    return {
        "status": "EXECUTED",
        "summary": f"recovered:{step.step_id}",
        "evidence": False,
    }


revision_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=4, max_steps=6, max_tool_calls=1),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "Solve task",
        }
    ],
    reasoner=revising_reasoner,
)
revision_task, _ = revision_engine.run("Revise if needed", deep_mode=True)
assert revision_task.status == TaskStatus.FINISHED
assert any(obs.requires_revision for obs in revision_task.observations)
print("revision flow: PASS")


runtime_path = root / "services" / "agent-runtime" / "runtime.py"
runtime_mod = load_module("shy_runtime_for_task_engine_test", runtime_path)

health_calls = {"count": 0}


def health_tool():
    health_calls["count"] += 1
    return {"status": "healthy"}


tool_gateway = runtime_mod.ToolGateway()
tool_gateway.register("system.health", health_tool)
actual_runtime = runtime_mod.AgentRuntime(gateway=tool_gateway)

tool_engine = TaskEngine(
    runtime=actual_runtime,
    limits=TaskLimits(max_iterations=3, max_steps=4, max_tool_calls=2),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "Check your health",
            "tool_name": "system.health",
        }
    ],
)
tool_task2, _ = tool_engine.run("Use system health", deep_mode=True)
assert tool_task2.status == TaskStatus.FINISHED
assert health_calls["count"] == 1
print("tool flow via runtime/gateway: PASS")


approval_runtime = FakeRuntime(
    SimpleNamespace(
        status="TOOL_RESULT",
        tool_name="message.send",
        tool_status="AWAITING_APPROVAL",
        output=None,
    )
)

approval_engine = TaskEngine(
    runtime=approval_runtime,
    limits=TaskLimits(max_iterations=3, max_steps=4, max_tool_calls=2),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "Send a message",
            "tool_name": "message.send",
        }
    ],
)
approval_task, _ = approval_engine.run("Send a message", deep_mode=True)
assert approval_task.status == TaskStatus.FAILED
assert approval_task.failure_reason == APPROVAL_REQUIRED
print("approval-required handling: PASS")


denied_runtime = FakeRuntime(
    SimpleNamespace(
        status="TOOL_RESULT",
        tool_name="unknown.tool",
        tool_status="DENIED",
        output=None,
    )
)

denied_engine = TaskEngine(
    runtime=denied_runtime,
    limits=TaskLimits(max_iterations=3, max_steps=4, max_tool_calls=2),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "Run denied tool",
            "tool_name": "unknown.tool",
        }
    ],
)
denied_task, _ = denied_engine.run("Run denied tool", deep_mode=True)
assert denied_task.status == TaskStatus.FAILED
assert denied_task.failure_reason == TOOL_DENIED
print("denied tool handling: PASS")


iteration_fail_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=1, max_steps=5, max_tool_calls=1),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "Needs retry",
        }
    ],
    reasoner=lambda _s, _t: {
        "status": "FAILED",
        "summary": "",
        "error_code": "TEMP_FAIL",
        "recoverable": True,
    },
)
iteration_fail_task, _ = iteration_fail_engine.run("force retries", deep_mode=True)
assert iteration_fail_task.status == TaskStatus.FAILED
assert iteration_fail_task.failure_reason == ITERATION_LIMIT_REACHED
print("deep iteration limit: PASS")


step_limit_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=2, max_steps=1, max_tool_calls=1),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "First",
        },
        {
            "step_id": 2,
            "action_type": "REASON",
            "objective": "Second",
        },
    ],
)
step_limit_task2, _ = step_limit_engine.run("too many steps", deep_mode=True)
assert step_limit_task2.status == TaskStatus.FAILED
assert step_limit_task2.failure_reason == STEP_LIMIT_REACHED
print("deep step limit: PASS")


tool_limit_runtime = FakeRuntime(
    SimpleNamespace(
        status="TOOL_RESULT",
        tool_name="system.health",
        tool_status="EXECUTED",
        output={"status": "healthy"},
    )
)

tool_limit_engine2 = TaskEngine(
    runtime=tool_limit_runtime,
    limits=TaskLimits(max_iterations=2, max_steps=4, max_tool_calls=0),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "TOOL",
            "objective": "Check your health",
            "tool_name": "system.health",
        }
    ],
)
tool_limit_task2, _ = tool_limit_engine2.run("health", deep_mode=True)
assert tool_limit_task2.status == TaskStatus.FAILED
assert tool_limit_task2.failure_reason == TOOL_CALL_LIMIT_REACHED
print("deep tool-call limit: PASS")


invalid_plan_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=2, max_steps=4, max_tool_calls=1),
    plan_builder=lambda _o, _t: [],
)
invalid_plan_task, _ = invalid_plan_engine.run("invalid plan", deep_mode=True)
assert invalid_plan_task.status == TaskStatus.FAILED
assert invalid_plan_task.failure_reason == INVALID_PLAN
print("invalid plan rejection: PASS")


verify_counter = {"count": 0}


def correctable_verifier(task):
    verify_counter["count"] += 1

    if verify_counter["count"] == 1:
        return VerificationResult(
            outcome=VerificationOutcome.CORRECTABLE,
            issues=(VerificationIssue.INSUFFICIENT_EVIDENCE,),
            summary="Need one more summarized step.",
        )

    return VerificationResult(
        outcome=VerificationOutcome.PASS,
        issues=(),
        summary="Verified.",
    )


correctable_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=4, max_steps=4, max_tool_calls=1),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "Generate summary",
        }
    ],
    reasoner=lambda s, _t: {
        "status": "EXECUTED",
        "summary": f"summary:{s.step_id}",
        "evidence": False,
    },
    verifier=correctable_verifier,
)
correctable_task, _ = correctable_engine.run("correctable verify", deep_mode=True)
assert correctable_task.status == TaskStatus.FINISHED
print("verification correctable path: PASS")


verify_fail_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=2, max_steps=4, max_tool_calls=1),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "Generate summary",
        }
    ],
    reasoner=lambda s, _t: {
        "status": "EXECUTED",
        "summary": f"summary:{s.step_id}",
        "evidence": False,
    },
    verifier=lambda _t: VerificationResult(
        outcome=VerificationOutcome.FAIL,
        issues=(VerificationIssue.UNSUPPORTED_OUTPUT,),
        summary="Cannot verify",
    ),
)
verify_fail_task, _ = verify_fail_engine.run("verify fail", deep_mode=True)
assert verify_fail_task.status == TaskStatus.FAILED
assert verify_fail_task.failure_reason == VERIFICATION_FAILED
print("verification failure path: PASS")


inconsistent_verifier_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=2, max_steps=4, max_tool_calls=1),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "Generate summary",
        }
    ],
    reasoner=lambda s, _t: {
        "status": "EXECUTED",
        "summary": f"summary:{s.step_id}",
        "evidence": False,
    },
    verifier=lambda _t: {
        "outcome": "FAIL",
        "issues": ["VERIFICATION_UNAVAILABLE"],
        "recommended_action": "FINISH",
        "summary": "Inconsistent verifier result.",
    },
)
inconsistent_task, _ = inconsistent_verifier_engine.run(
    "inconsistent verifier",
    deep_mode=True,
)
assert inconsistent_task.status == TaskStatus.FAILED
assert inconsistent_task.failure_reason == VERIFICATION_FAILED
print("inconsistent verifier routing fails safely: PASS")


unknown_outcome_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=2, max_steps=4, max_tool_calls=1),
    plan_builder=lambda _o, _t: [
        {
            "step_id": 1,
            "action_type": "REASON",
            "objective": "Generate summary",
        }
    ],
    reasoner=lambda s, _t: {
        "status": "EXECUTED",
        "summary": f"summary:{s.step_id}",
        "evidence": False,
    },
    verifier=lambda _t: {
        "outcome": "UNKNOWN_OUTCOME",
        "issues": [],
        "summary": "Unsupported outcome.",
    },
)
unknown_outcome_task, _ = unknown_outcome_engine.run(
    "unknown outcome verifier",
    deep_mode=True,
)
assert unknown_outcome_task.status == TaskStatus.FAILED
assert unknown_outcome_task.failure_reason == VERIFICATION_FAILED
print("unknown verifier outcome fails safely: PASS")


compat_runtime = FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None))
compatibility_engine = TaskEngine(
    runtime=compat_runtime,
    limits=TaskLimits(max_iterations=2, max_steps=8, max_tool_calls=1),
    compatibility_mode=True,
)
compat_task, compat_result = compatibility_engine.run("Hello again")
assert compat_result.status == "RESPOND"
assert compat_task.status == TaskStatus.FINISHED
assert compat_runtime.calls == 1
print("compatibility mode unchanged: PASS")


deterministic_engine = TaskEngine(
    runtime=FakeRuntime(SimpleNamespace(status="RESPOND", tool_name=None)),
    limits=TaskLimits(max_iterations=3, max_steps=4, max_tool_calls=1),
    plan_builder=lambda _o, _t: [
        PlanStep(
            step_id=1,
            action_type=ActionType.REASON,
            objective="Do deterministic work",
        )
    ],
    reasoner=lambda s, _t: {
        "status": "EXECUTED",
        "summary": f"det:{s.step_id}",
        "evidence": False,
    },
    verifier=lambda _t: VerificationResult(
        outcome=VerificationOutcome.PASS,
        issues=(),
        summary="ok",
    ),
)
det1, _ = deterministic_engine.run("same input", deep_mode=True)
det2, _ = deterministic_engine.run("same input", deep_mode=True)

sig1 = [
    (s.step_id, s.action_type.value, s.status.value, s.result_summary)
    for s in det1.plan_steps
]
sig2 = [
    (s.step_id, s.action_type.value, s.status.value, s.result_summary)
    for s in det2.plan_steps
]
assert sig1 == sig2
print("deep-mode determinism: PASS")


forbidden_fields = (
    "chain_of_thought",
    "scratchpad",
    "internal_monologue",
    "reasoning_trace",
    "hidden_reasoning",
)

task_dict = vars(det1)
for forbidden in forbidden_fields:
    assert forbidden not in task_dict

for step in det1.plan_steps:
    step_dict = vars(step)
    for forbidden in forbidden_fields:
        assert forbidden not in step_dict

for observation in det1.observations:
    observation_dict = vars(observation)
    for forbidden in forbidden_fields:
        assert forbidden not in observation_dict

print("no private reasoning artifacts: PASS")

print("SHY Phase 2 task engine tests: PASS")
