import importlib.util
import time
from pathlib import Path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent_runtime_path = Path(__file__).resolve().parent

loop_module = load_module(
    "shy_loop_state",
    agent_runtime_path / "loop_state.py",
)

TaskEngineState = loop_module.TaskEngineState
TaskStepArtifact = loop_module.TaskStepArtifact
TaskState = loop_module.TaskState
TaskLimits = loop_module.TaskLimits
TaskStatus = loop_module.TaskStatus
VerificationStatus = loop_module.VerificationStatus
ITERATION_LIMIT_REACHED = loop_module.ITERATION_LIMIT_REACHED
STEP_LIMIT_REACHED = loop_module.STEP_LIMIT_REACHED
TOOL_CALL_LIMIT_REACHED = loop_module.TOOL_CALL_LIMIT_REACHED


class TaskEngine:
    """
    SHY TaskEngine Phase 1.

    Compatibility mode preserves v0.10 behavior by performing a single
    AgentRuntime call while recording structured task artifacts.
    """

    def __init__(
        self,
        runtime,
        limits: TaskLimits | None = None,
        compatibility_mode: bool = True,
    ):
        self.runtime = runtime
        self.limits = limits or TaskLimits()
        self.compatibility_mode = compatibility_mode

    def create_task(
        self,
        objective: str,
        verification_required: bool = False,
    ) -> TaskState:
        return TaskState.create(
            objective=objective,
            verification_required=verification_required,
        )

    def run(self, objective: str) -> tuple[TaskState, object | None]:
        if self.compatibility_mode:
            return self.run_compatibility_mode(objective)

        task = self.create_task(objective=objective)
        task.transition_to(
            TaskEngineState.FAILED,
            failure_reason="DEEP_LOOP_NOT_IMPLEMENTED",
        )
        return task, None

    def run_compatibility_mode(
        self,
        objective: str,
    ) -> tuple[TaskState, object | None]:
        task = self.create_task(objective=objective)

        if not self.advance(task, TaskEngineState.PLAN, label="understand"):
            return task, None

        if not self.advance(task, TaskEngineState.EXECUTE, label="plan"):
            return task, None

        if self.runtime is None:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason="RUNTIME_UNAVAILABLE",
            )
            return task, None

        result = self.runtime.run(objective)

        if getattr(result, "status", None) == "TOOL_RESULT":
            task.tool_call_count += 1

            if task.tool_call_count > self.limits.max_tool_calls:
                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason=TOOL_CALL_LIMIT_REACHED,
                )
                return task, result

        self._append_step(
            task,
            state=TaskEngineState.EXECUTE,
            label="runtime",
            result_status=getattr(result, "status", None),
            tool_name=getattr(result, "tool_name", None),
        )

        if not self.advance(task, TaskEngineState.FINISH, label="observe"):
            return task, result

        return task, result

    def advance(
        self,
        task: TaskState,
        new_state: TaskEngineState,
        label: str,
    ) -> bool:
        if task.status != TaskStatus.RUNNING:
            return False

        if task.state in (TaskEngineState.FINISH, TaskEngineState.FAILED):
            return False

        if task.state in (TaskEngineState.UNDERSTAND, TaskEngineState.REVISE):
            if new_state in (TaskEngineState.PLAN, TaskEngineState.EXECUTE):
                task.iteration_count += 1

                if task.iteration_count > self.limits.max_iterations:
                    task.transition_to(
                        TaskEngineState.FAILED,
                        failure_reason=ITERATION_LIMIT_REACHED,
                    )
                    return False

        if not self._check_limits(task):
            return False

        task.transition_to(new_state)
        self._append_step(task, state=new_state, label=label)

        return True

    def _check_limits(self, task: TaskState) -> bool:
        if len(task.steps) >= self.limits.max_steps:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=STEP_LIMIT_REACHED,
            )
            return False

        if task.tool_call_count > self.limits.max_tool_calls:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=TOOL_CALL_LIMIT_REACHED,
            )
            return False

        if self.limits.max_seconds is not None:
            elapsed_seconds = time.time() - task.started_at

            if elapsed_seconds > self.limits.max_seconds:
                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason="TIME_BUDGET_EXCEEDED",
                )
                return False

        return True

    @staticmethod
    def _append_step(
        task: TaskState,
        state: TaskEngineState,
        label: str,
        result_status: str | None = None,
        tool_name: str | None = None,
    ):
        artifact = TaskStepArtifact(
            index=len(task.steps),
            state=state,
            label=label,
            result_status=result_status,
            tool_name=tool_name,
        )

        task.steps.append(artifact)
        task.current_step = artifact.index
