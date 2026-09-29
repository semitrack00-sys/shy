import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class TaskEngineState(str, Enum):
    UNDERSTAND = "UNDERSTAND"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    OBSERVE = "OBSERVE"
    REVISE = "REVISE"
    VERIFY = "VERIFY"
    FINISH = "FINISH"
    FAILED = "FAILED"


class TaskStatus(str, Enum):
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


class VerificationStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"


ITERATION_LIMIT_REACHED = "ITERATION_LIMIT_REACHED"
STEP_LIMIT_REACHED = "STEP_LIMIT_REACHED"
TOOL_CALL_LIMIT_REACHED = "TOOL_CALL_LIMIT_REACHED"


@dataclass(frozen=True)
class TaskLimits:
    max_iterations: int = 1
    max_tool_calls: int = 1
    max_steps: int = 6
    max_seconds: float | None = None
    max_tokens: int | None = None

    def __post_init__(self):
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        if self.max_tool_calls < 0:
            raise ValueError("max_tool_calls cannot be negative")
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1")


@dataclass
class TaskStepArtifact:
    index: int
    state: TaskEngineState
    label: str
    result_status: str | None = None
    tool_name: str | None = None


@dataclass
class TaskState:
    task_id: str
    objective: str
    state: TaskEngineState = TaskEngineState.UNDERSTAND
    steps: list[TaskStepArtifact] = field(default_factory=list)
    current_step: int | None = None
    iteration_count: int = 0
    tool_call_count: int = 0
    started_at: float = field(default_factory=time.time)
    status: TaskStatus = TaskStatus.RUNNING
    verification_status: VerificationStatus = VerificationStatus.NOT_REQUIRED
    failure_reason: str | None = None

    @classmethod
    def create(
        cls,
        objective: str,
        verification_required: bool = False,
        task_id: str | None = None,
    ):
        verification_status = VerificationStatus.NOT_REQUIRED

        if verification_required:
            verification_status = VerificationStatus.PENDING

        return cls(
            task_id=task_id or str(uuid.uuid4()),
            objective=objective,
            verification_status=verification_status,
        )

    def transition_to(
        self,
        new_state: TaskEngineState,
        failure_reason: str | None = None,
    ):
        allowed = _ALLOWED_TRANSITIONS[self.state]

        if new_state not in allowed:
            raise ValueError(
                f"Invalid transition from {self.state.value} to {new_state.value}."
            )

        self.state = new_state

        if new_state == TaskEngineState.FINISH:
            self.status = TaskStatus.FINISHED

            if self.verification_status == VerificationStatus.PENDING:
                self.verification_status = VerificationStatus.PASSED

        if new_state == TaskEngineState.FAILED:
            self.status = TaskStatus.FAILED
            self.failure_reason = failure_reason or "TASK_FAILED"


_ALLOWED_TRANSITIONS = {
    TaskEngineState.UNDERSTAND: {
        TaskEngineState.PLAN,
        TaskEngineState.FAILED,
    },
    TaskEngineState.PLAN: {
        TaskEngineState.EXECUTE,
        TaskEngineState.FAILED,
    },
    TaskEngineState.EXECUTE: {
        TaskEngineState.OBSERVE,
        TaskEngineState.FINISH,
        TaskEngineState.FAILED,
    },
    TaskEngineState.OBSERVE: {
        TaskEngineState.REVISE,
        TaskEngineState.VERIFY,
        TaskEngineState.FINISH,
        TaskEngineState.FAILED,
    },
    TaskEngineState.REVISE: {
        TaskEngineState.PLAN,
        TaskEngineState.EXECUTE,
        TaskEngineState.FAILED,
    },
    TaskEngineState.VERIFY: {
        TaskEngineState.REVISE,
        TaskEngineState.FINISH,
        TaskEngineState.FAILED,
    },
    TaskEngineState.FINISH: set(),
    TaskEngineState.FAILED: set(),
}
