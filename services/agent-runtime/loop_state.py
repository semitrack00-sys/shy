import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


DEFAULT_MAX_STEPS = 5
HARD_MAX_STEPS = 8


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
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FINISHED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


class VerificationStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class ActionType(str, Enum):
    REASON = "REASON"
    TOOL = "TOOL"


class PlanStepStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class VerificationOutcome(str, Enum):
    PASS = "PASS"
    CORRECTABLE = "CORRECTABLE"
    FAIL = "FAIL"


class VerificationIssue(str, Enum):
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    CITATION_INVALID = "CITATION_INVALID"
    CITATION_MISMATCH = "CITATION_MISMATCH"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    TOOL_RESULT_MISMATCH = "TOOL_RESULT_MISMATCH"
    INCOMPLETE_RESULT = "INCOMPLETE_RESULT"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"
    MISSING_RESULT = "MISSING_RESULT"
    TOOL_FAILURE = "TOOL_FAILURE"
    INCOMPLETE_PLAN = "INCOMPLETE_PLAN"
    UNSUPPORTED_OUTPUT = "UNSUPPORTED_OUTPUT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    LIMIT_REACHED = "LIMIT_REACHED"


ITERATION_LIMIT_REACHED = "ITERATION_LIMIT_REACHED"
STEP_LIMIT_REACHED = "STEP_LIMIT_REACHED"
TOOL_CALL_LIMIT_REACHED = "TOOL_CALL_LIMIT_REACHED"
TIME_LIMIT_REACHED = "TIME_LIMIT_REACHED"

INVALID_PLAN = "INVALID_PLAN"
PLANNER_FAILURE = "PLANNER_FAILURE"
RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
TOOL_DENIED = "TOOL_DENIED"
TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
REASONING_OPERATION_FAILED = "REASONING_OPERATION_FAILED"
VERIFICATION_FAILED = "VERIFICATION_FAILED"


@dataclass(frozen=True)
class TaskLimits:
    max_iterations: int = 1
    max_tool_calls: int = 1
    max_steps: int = DEFAULT_MAX_STEPS
    max_seconds: float | None = None
    max_tokens: int | None = None

    def __post_init__(self):
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        if self.max_tool_calls < 0:
            raise ValueError("max_tool_calls cannot be negative")
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1")
        if self.max_steps > HARD_MAX_STEPS:
            object.__setattr__(self, "max_steps", HARD_MAX_STEPS)


@dataclass
class TaskStepArtifact:
    index: int
    state: TaskEngineState
    label: str
    result_status: str | None = None
    tool_name: str | None = None


@dataclass
class PlanStep:
    step_id: int
    action_type: ActionType
    objective: str
    status: PlanStepStatus = PlanStepStatus.PENDING
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    result_summary: str | None = None
    error: str | None = None
    retry_count: int = 0

    def __post_init__(self):
        if self.step_id < 1:
            raise ValueError("step_id must be at least 1")

        if not self.objective.strip():
            raise ValueError("objective cannot be empty")

        if self.action_type == ActionType.TOOL and not self.tool_name:
            raise ValueError("tool steps must provide tool_name")


@dataclass
class StepObservation:
    step_id: int
    status: str
    result_available: bool
    evidence_available: bool
    error_code: str | None = None
    requires_revision: bool = False


@dataclass(frozen=True)
class VerificationResult:
    outcome: VerificationOutcome
    issues: tuple[VerificationIssue, ...] = ()
    summary: str = ""


TaskStep = PlanStep


@dataclass
class StepResult:
    step_id: int
    status: str
    tool_name: str | None = None
    sanitized_output: Any = None
    result_summary: str | None = None
    failure_category: str | None = None
    retry_count: int = 0


@dataclass
class TaskPlan:
    goal: str
    steps: list[TaskStep]
    maximum_step_count: int = DEFAULT_MAX_STEPS
    current_step: int = 0
    completion_criteria: str = ""
    failure_policy: str = ""

    def __post_init__(self):
        if not self.goal.strip():
            raise ValueError("goal cannot be empty")
        if self.maximum_step_count < 1:
            raise ValueError("maximum_step_count must be at least 1")
        if self.maximum_step_count > HARD_MAX_STEPS:
            self.maximum_step_count = HARD_MAX_STEPS


@dataclass
class TaskExecutionContext:
    mode: str = "DIRECT"
    max_steps: int = DEFAULT_MAX_STEPS
    hard_max_steps: int = HARD_MAX_STEPS
    completion_criteria: str = ""
    failure_policy: str = ""
    retry_budget_per_step: int = 1
    step_results: list[StepResult] = field(default_factory=list)
    derived_values: dict[str, Any] = field(default_factory=dict)
    awaiting_step_id: int | None = None
    awaiting_tool_name: str | None = None
    approval_token: str | None = None


@dataclass
class TaskState:
    task_id: str
    objective: str
    state: TaskEngineState = TaskEngineState.UNDERSTAND
    steps: list[TaskStepArtifact] = field(default_factory=list)
    plan_steps: list[PlanStep] = field(default_factory=list)
    observations: list[StepObservation] = field(default_factory=list)
    capabilities: tuple[str, ...] = ()
    current_step: int | None = None
    iteration_count: int = 0
    tool_call_count: int = 0
    started_at: float = field(default_factory=time.time)
    started_monotonic: float = field(default_factory=time.monotonic)
    status: TaskStatus = TaskStatus.RUNNING
    verification_status: VerificationStatus = VerificationStatus.NOT_REQUIRED
    verification_result: VerificationResult | None = None
    verification_report: dict[str, Any] | None = None
    failure_reason: str | None = None
    plan: TaskPlan | None = None
    execution_context: TaskExecutionContext = field(default_factory=TaskExecutionContext)

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
            self.status = TaskStatus.COMPLETED

            if self.verification_status == VerificationStatus.PENDING:
                self.verification_status = VerificationStatus.PASSED

        if new_state == TaskEngineState.FAILED:
            self.status = TaskStatus.FAILED
            self.verification_status = VerificationStatus.FAILED
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
