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
ITERATION_LIMIT_REACHED = loop_module.ITERATION_LIMIT_REACHED
STEP_LIMIT_REACHED = loop_module.STEP_LIMIT_REACHED
TOOL_CALL_LIMIT_REACHED = loop_module.TOOL_CALL_LIMIT_REACHED
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

print("SHY Phase 1 task engine tests: PASS")
