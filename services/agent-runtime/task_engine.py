import importlib.util
import time
from pathlib import Path
from typing import Any


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
ActionType = loop_module.ActionType
PlanStep = loop_module.PlanStep
PlanStepStatus = loop_module.PlanStepStatus
StepObservation = loop_module.StepObservation
VerificationResult = loop_module.VerificationResult
VerificationOutcome = loop_module.VerificationOutcome
VerificationIssue = loop_module.VerificationIssue
ITERATION_LIMIT_REACHED = loop_module.ITERATION_LIMIT_REACHED
STEP_LIMIT_REACHED = loop_module.STEP_LIMIT_REACHED
TOOL_CALL_LIMIT_REACHED = loop_module.TOOL_CALL_LIMIT_REACHED
TIME_LIMIT_REACHED = loop_module.TIME_LIMIT_REACHED
INVALID_PLAN = loop_module.INVALID_PLAN
PLANNER_FAILURE = loop_module.PLANNER_FAILURE
RUNTIME_UNAVAILABLE = loop_module.RUNTIME_UNAVAILABLE
APPROVAL_REQUIRED = loop_module.APPROVAL_REQUIRED
TOOL_DENIED = loop_module.TOOL_DENIED
TOOL_EXECUTION_FAILED = loop_module.TOOL_EXECUTION_FAILED
REASONING_OPERATION_FAILED = loop_module.REASONING_OPERATION_FAILED
VERIFICATION_FAILED = loop_module.VERIFICATION_FAILED


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
        plan_builder=None,
        reasoner=None,
        verifier=None,
        clock=None,
    ):
        self.runtime = runtime
        self.limits = limits or TaskLimits()
        self.compatibility_mode = compatibility_mode
        self.plan_builder = plan_builder or self._default_plan_builder
        self.reasoner = reasoner or self._default_reasoner
        self.verifier = verifier or self._default_verifier
        self.clock = clock or time.monotonic

    def create_task(
        self,
        objective: str,
        verification_required: bool = False,
    ) -> TaskState:
        return TaskState.create(
            objective=objective,
            verification_required=verification_required,
        )

    def run(
        self,
        objective: str,
        deep_mode: bool = False,
    ) -> tuple[TaskState, object | None]:
        if not deep_mode and self.compatibility_mode:
            return self.run_compatibility_mode(objective)

        return self.run_deep_mode(objective)

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
                failure_reason=RUNTIME_UNAVAILABLE,
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
        if task.plan_steps:
            if len(task.plan_steps) > self.limits.max_steps:
                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason=STEP_LIMIT_REACHED,
                )
                return False
        else:
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
            elapsed_seconds = self.clock() - task.started_monotonic

            if elapsed_seconds > self.limits.max_seconds:
                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason=TIME_LIMIT_REACHED,
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

    def run_deep_mode(self, objective: str) -> tuple[TaskState, dict[str, Any] | None]:
        task = self.create_task(
            objective=objective,
            verification_required=True,
        )

        if not self.advance(task, TaskEngineState.PLAN, label="understand"):
            return task, None

        plan = self._build_plan(task)

        if plan is None:
            return task, None

        task.plan_steps = plan

        while task.status == TaskStatus.RUNNING:
            if not self._check_limits(task):
                break

            pending_step = self._next_pending_step(task)

            if pending_step is None:
                if task.state == TaskEngineState.PLAN:
                    if not self.advance(task, TaskEngineState.EXECUTE, label="plan-empty"):
                        break

                if task.state == TaskEngineState.EXECUTE:
                    if not self.advance(task, TaskEngineState.OBSERVE, label="execute-empty"):
                        break

                if not self.advance(task, TaskEngineState.VERIFY, label="observe"):
                    break

                verification = self._verify(task)
                task.verification_result = verification

                if verification.outcome == VerificationOutcome.PASS:
                    task.verification_status = VerificationStatus.PASSED
                    self._mark_remaining_steps_skipped(task)
                    self.advance(task, TaskEngineState.FINISH, label="verify")
                    break

                if verification.outcome == VerificationOutcome.CORRECTABLE:
                    if not self._enter_revision(task):
                        break

                    self._revise_plan(task, reason="VERIFICATION_CORRECTABLE")

                    if not self.advance(task, TaskEngineState.PLAN, label="revise"):
                        break

                    continue

                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason=VERIFICATION_FAILED,
                )
                break

            if not self.advance(task, TaskEngineState.EXECUTE, label="plan"):
                break

            execution = self._execute_plan_step(task, pending_step)

            if task.status != TaskStatus.RUNNING:
                break

            if not self.advance(task, TaskEngineState.OBSERVE, label="execute"):
                break

            observation = self._observe_step(
                step=pending_step,
                execution=execution,
            )
            task.observations.append(observation)

            if observation.error_code in (APPROVAL_REQUIRED, TOOL_DENIED):
                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason=observation.error_code,
                )
                break

            if observation.requires_revision:
                if not self._enter_revision(task):
                    break

                self._revise_plan(
                    task,
                    failed_step=pending_step,
                    reason=observation.error_code,
                )

                if not self.advance(task, TaskEngineState.PLAN, label="revise"):
                    break

                continue

            if self._next_pending_step(task) is not None:
                if not self._enter_revision(task):
                    break

                self._revise_plan(task, reason="CONTINUE_PLAN")

                if not self.advance(task, TaskEngineState.PLAN, label="revise"):
                    break

                continue

        payload = {
            "plan_steps": len(task.plan_steps),
            "observations": len(task.observations),
            "verification": (
                task.verification_result.outcome.value
                if task.verification_result is not None
                else None
            ),
        }

        return task, payload

    def _build_plan(self, task: TaskState) -> list[PlanStep] | None:
        try:
            raw_plan = self.plan_builder(task.objective, task)
        except Exception:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=PLANNER_FAILURE,
            )
            return None

        if not isinstance(raw_plan, list) or not raw_plan:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=INVALID_PLAN,
            )
            return None

        if len(raw_plan) > self.limits.max_steps:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=STEP_LIMIT_REACHED,
            )
            return None

        plan_steps: list[PlanStep] = []

        for index, raw_step in enumerate(raw_plan, start=1):
            try:
                plan_steps.append(self._coerce_plan_step(raw_step, index))
            except Exception:
                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason=INVALID_PLAN,
                )
                return None

        return plan_steps

    @staticmethod
    def _coerce_plan_step(raw_step: Any, index: int) -> PlanStep:
        if isinstance(raw_step, PlanStep):
            return raw_step

        if not isinstance(raw_step, dict):
            raise ValueError("plan step must be a PlanStep or dict")

        action_type = raw_step.get("action_type")

        if isinstance(action_type, str):
            action_type = ActionType(action_type)

        if action_type not in (ActionType.REASON, ActionType.TOOL):
            raise ValueError("unsupported action type")

        status = raw_step.get("status", PlanStepStatus.PENDING)

        if isinstance(status, str):
            status = PlanStepStatus(status)

        return PlanStep(
            step_id=int(raw_step.get("step_id", index)),
            action_type=action_type,
            objective=str(raw_step.get("objective", "")).strip(),
            status=status,
            tool_name=raw_step.get("tool_name"),
            tool_args=raw_step.get("tool_args"),
            result_summary=raw_step.get("result_summary"),
            error=raw_step.get("error"),
        )

    @staticmethod
    def _next_pending_step(task: TaskState) -> PlanStep | None:
        for step in task.plan_steps:
            if step.status == PlanStepStatus.PENDING:
                return step
        return None

    def _execute_plan_step(self, task: TaskState, step: PlanStep) -> dict[str, Any]:
        if step.action_type == ActionType.TOOL:
            return self._execute_tool_step(task, step)

        return self._execute_reasoning_step(task, step)

    def _execute_tool_step(self, task: TaskState, step: PlanStep) -> dict[str, Any]:
        if self.runtime is None:
            step.status = PlanStepStatus.FAILED
            step.error = RUNTIME_UNAVAILABLE

            return {
                "status": "FAILED",
                "result_available": False,
                "evidence_available": False,
                "error_code": RUNTIME_UNAVAILABLE,
                "recoverable": False,
            }

        task.tool_call_count += 1

        if task.tool_call_count > self.limits.max_tool_calls:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=TOOL_CALL_LIMIT_REACHED,
            )

            step.status = PlanStepStatus.FAILED
            step.error = TOOL_CALL_LIMIT_REACHED

            return {
                "status": "FAILED",
                "result_available": False,
                "evidence_available": False,
                "error_code": TOOL_CALL_LIMIT_REACHED,
                "recoverable": False,
            }

        runtime_result = self.runtime.run(step.objective)
        tool_status = getattr(runtime_result, "tool_status", None)
        result_status = getattr(runtime_result, "status", None)
        tool_name = getattr(runtime_result, "tool_name", step.tool_name)

        step.result_summary = (
            f"status={result_status};"
            f"tool={tool_name};"
            f"tool_status={tool_status}"
        )

        if result_status != "TOOL_RESULT":
            step.status = PlanStepStatus.FAILED
            step.error = "UNSUPPORTED_OUTPUT"

            return {
                "status": "FAILED",
                "result_available": False,
                "evidence_available": False,
                "error_code": "UNSUPPORTED_OUTPUT",
                "recoverable": False,
            }

        if tool_status == "EXECUTED":
            step.status = PlanStepStatus.EXECUTED

            output = getattr(runtime_result, "output", None)

            return {
                "status": "EXECUTED",
                "result_available": output is not None,
                "evidence_available": output is not None,
                "error_code": None,
                "recoverable": False,
            }

        if tool_status == "AWAITING_APPROVAL":
            step.status = PlanStepStatus.FAILED
            step.error = APPROVAL_REQUIRED

            return {
                "status": "FAILED",
                "result_available": False,
                "evidence_available": False,
                "error_code": APPROVAL_REQUIRED,
                "recoverable": False,
            }

        if tool_status == "DENIED":
            step.status = PlanStepStatus.FAILED
            step.error = TOOL_DENIED

            return {
                "status": "FAILED",
                "result_available": False,
                "evidence_available": False,
                "error_code": TOOL_DENIED,
                "recoverable": False,
            }

        step.status = PlanStepStatus.FAILED
        step.error = TOOL_EXECUTION_FAILED

        return {
            "status": "FAILED",
            "result_available": False,
            "evidence_available": False,
            "error_code": TOOL_EXECUTION_FAILED,
            "recoverable": tool_status in ("FAILED", "UNAVAILABLE"),
        }

    def _execute_reasoning_step(self, task: TaskState, step: PlanStep) -> dict[str, Any]:
        try:
            result = self.reasoner(step, task)
        except Exception:
            step.status = PlanStepStatus.FAILED
            step.error = REASONING_OPERATION_FAILED

            return {
                "status": "FAILED",
                "result_available": False,
                "evidence_available": False,
                "error_code": REASONING_OPERATION_FAILED,
                "recoverable": True,
            }

        if not isinstance(result, dict):
            step.status = PlanStepStatus.FAILED
            step.error = "UNSUPPORTED_OUTPUT"

            return {
                "status": "FAILED",
                "result_available": False,
                "evidence_available": False,
                "error_code": "UNSUPPORTED_OUTPUT",
                "recoverable": False,
            }

        status = result.get("status", "FAILED")
        summary = str(result.get("summary", "")).strip()
        recoverable = bool(result.get("recoverable", status != "EXECUTED"))

        if status == "EXECUTED" and summary:
            step.status = PlanStepStatus.EXECUTED
            step.result_summary = summary

            return {
                "status": "EXECUTED",
                "result_available": True,
                "evidence_available": bool(result.get("evidence", False)),
                "error_code": None,
                "recoverable": False,
            }

        step.status = PlanStepStatus.FAILED
        step.error = result.get("error_code", REASONING_OPERATION_FAILED)

        return {
            "status": "FAILED",
            "result_available": False,
            "evidence_available": False,
            "error_code": step.error,
            "recoverable": recoverable,
        }

    @staticmethod
    def _observe_step(step: PlanStep, execution: dict[str, Any]) -> StepObservation:
        return StepObservation(
            step_id=step.step_id,
            status=execution.get("status", "FAILED"),
            result_available=bool(execution.get("result_available", False)),
            evidence_available=bool(execution.get("evidence_available", False)),
            error_code=execution.get("error_code"),
            requires_revision=bool(execution.get("recoverable", False)),
        )

    def _enter_revision(self, task: TaskState) -> bool:
        if task.iteration_count >= self.limits.max_iterations:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=ITERATION_LIMIT_REACHED,
            )
            return False

        return self.advance(task, TaskEngineState.REVISE, label="observe")

    def _revise_plan(
        self,
        task: TaskState,
        failed_step: PlanStep | None = None,
        reason: str | None = None,
    ):
        if failed_step is not None and failed_step.status == PlanStepStatus.FAILED:
            failed_step.status = PlanStepStatus.PENDING
            failed_step.error = None

        if reason == "VERIFICATION_CORRECTABLE":
            for step in task.plan_steps:
                if step.status == PlanStepStatus.PENDING:
                    return

            if len(task.plan_steps) >= self.limits.max_steps:
                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason=STEP_LIMIT_REACHED,
                )
                return

            task.plan_steps.append(
                PlanStep(
                    step_id=len(task.plan_steps) + 1,
                    action_type=ActionType.REASON,
                    objective="Produce a complete structured response summary.",
                )
            )

    @staticmethod
    def _mark_remaining_steps_skipped(task: TaskState):
        for step in task.plan_steps:
            if step.status == PlanStepStatus.PENDING:
                step.status = PlanStepStatus.SKIPPED

    def _verify(self, task: TaskState) -> VerificationResult:
        try:
            result = self.verifier(task)
        except Exception:
            return VerificationResult(
                outcome=VerificationOutcome.FAIL,
                issues=(VerificationIssue.UNSUPPORTED_OUTPUT,),
                summary="Verifier raised an exception.",
            )

        coerced = self._coerce_verification_result(result)

        if coerced is None:
            return VerificationResult(
                outcome=VerificationOutcome.FAIL,
                issues=(VerificationIssue.UNSUPPORTED_OUTPUT,),
                summary="Verifier returned an unsupported structure.",
            )

        return coerced

    @staticmethod
    def _coerce_verification_result(result: Any) -> VerificationResult | None:
        if isinstance(result, VerificationResult):
            return result

        if isinstance(result, dict):
            raw_outcome = result.get("outcome")
            raw_issues = result.get("issues", ())
            summary = str(result.get("summary", ""))
        else:
            raw_outcome = getattr(result, "outcome", None)
            raw_issues = getattr(result, "issues", ())
            summary = str(getattr(result, "summary", ""))

        try:
            normalized_outcome = getattr(raw_outcome, "value", raw_outcome)

            if isinstance(raw_outcome, VerificationOutcome):
                outcome = raw_outcome
            else:
                outcome = VerificationOutcome(str(normalized_outcome))

            issues: list[VerificationIssue] = []

            for issue in raw_issues:
                normalized_issue = getattr(issue, "value", issue)

                if isinstance(issue, VerificationIssue):
                    issues.append(issue)
                else:
                    issues.append(VerificationIssue(str(normalized_issue)))

            return VerificationResult(
                outcome=outcome,
                issues=tuple(issues),
                summary=summary,
            )
        except Exception:
            return None

    @staticmethod
    def _default_plan_builder(objective: str, task: TaskState) -> list[dict[str, Any]]:
        text = objective.lower().strip()

        if not text:
            return [
                {
                    "step_id": 1,
                    "action_type": "REASON",
                    "objective": "Generate a concise response.",
                }
            ]

        if text.startswith("research ") or text.startswith("search the web "):
            return [
                {
                    "step_id": 1,
                    "action_type": "TOOL",
                    "objective": objective,
                    "tool_name": "web.search",
                    "tool_args": {},
                },
                {
                    "step_id": 2,
                    "action_type": "REASON",
                    "objective": "Synthesize evidence into a grounded response.",
                },
            ]

        if "system health" in text or "check your health" in text:
            return [
                {
                    "step_id": 1,
                    "action_type": "TOOL",
                    "objective": objective,
                    "tool_name": "system.health",
                    "tool_args": {},
                }
            ]

        if any(term in text for term in ("compare", "constraints", "multi-stage", "plan")):
            return [
                {
                    "step_id": 1,
                    "action_type": "REASON",
                    "objective": "Structure requirements and constraints.",
                },
                {
                    "step_id": 2,
                    "action_type": "REASON",
                    "objective": "Produce staged recommendations.",
                },
            ]

        return [
            {
                "step_id": 1,
                "action_type": "REASON",
                "objective": "Generate a direct helpful response.",
            }
        ]

    @staticmethod
    def _default_reasoner(step: PlanStep, task: TaskState) -> dict[str, Any]:
        return {
            "status": "EXECUTED",
            "summary": f"Completed reasoning step {step.step_id}: {step.objective}",
            "evidence": False,
        }

    @staticmethod
    def _default_verifier(task: TaskState) -> VerificationResult:
        if not task.plan_steps:
            return VerificationResult(
                outcome=VerificationOutcome.FAIL,
                issues=(VerificationIssue.INCOMPLETE_PLAN,),
                summary="No plan steps exist.",
            )

        executed = [
            step for step in task.plan_steps if step.status == PlanStepStatus.EXECUTED
        ]
        failed = [step for step in task.plan_steps if step.status == PlanStepStatus.FAILED]
        pending = [
            step for step in task.plan_steps if step.status == PlanStepStatus.PENDING
        ]

        if failed:
            issue = VerificationIssue.TOOL_FAILURE

            if any(step.action_type == ActionType.REASON for step in failed):
                issue = VerificationIssue.UNSUPPORTED_OUTPUT

            return VerificationResult(
                outcome=VerificationOutcome.FAIL,
                issues=(issue,),
                summary="At least one plan step failed.",
            )

        if pending:
            return VerificationResult(
                outcome=VerificationOutcome.CORRECTABLE,
                issues=(VerificationIssue.INCOMPLETE_PLAN,),
                summary="Plan has pending work.",
            )

        if not executed:
            return VerificationResult(
                outcome=VerificationOutcome.FAIL,
                issues=(VerificationIssue.MISSING_RESULT,),
                summary="No executed results are available.",
            )

        if any(step.result_summary is None for step in executed):
            return VerificationResult(
                outcome=VerificationOutcome.CORRECTABLE,
                issues=(VerificationIssue.MISSING_RESULT,),
                summary="Executed steps are missing result summaries.",
            )

        return VerificationResult(
            outcome=VerificationOutcome.PASS,
            issues=(),
            summary="Plan execution is complete.",
        )
