import importlib.util
import ast
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

verifier_module = load_module(
    "shy_task_verifier",
    agent_runtime_path / "verifier.py",
)

TaskEngineState = loop_module.TaskEngineState
TaskStepArtifact = loop_module.TaskStepArtifact
TaskState = loop_module.TaskState
TaskLimits = loop_module.TaskLimits
TaskStatus = loop_module.TaskStatus
TaskPlan = loop_module.TaskPlan
TaskExecutionContext = loop_module.TaskExecutionContext
StepResult = loop_module.StepResult
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
        semantic_verifier=None,
        clock=None,
    ):
        self.runtime = runtime
        self.limits = limits or TaskLimits()
        self.compatibility_mode = compatibility_mode
        self.plan_builder = plan_builder or self._default_plan_builder
        self.reasoner = reasoner or self._default_reasoner
        self.verifier = verifier or self._default_verifier
        self.semantic_verifier = semantic_verifier
        self.clock = clock or time.monotonic

    def create_task(
        self,
        objective: str,
        verification_required: bool = False,
        execution_mode: str = "DIRECT",
        completion_criteria: str = "",
        failure_policy: str = "",
    ) -> TaskState:
        task = TaskState.create(
            objective=objective,
            verification_required=verification_required,
        )
        task.execution_context = TaskExecutionContext(
            mode=execution_mode,
            max_steps=self.limits.max_steps,
            completion_criteria=completion_criteria,
            failure_policy=failure_policy,
        )
        return task

    def resume_task(
        self,
        task: TaskState,
        approval_token: str,
    ) -> tuple[TaskState, dict[str, Any] | None]:
        if task.status != TaskStatus.AWAITING_APPROVAL:
            raise ValueError("Task is not awaiting approval.")

        task.status = TaskStatus.RUNNING
        task.execution_context.approval_token = approval_token
        return self._drive_task(task)

    @staticmethod
    def cancel_task(task: TaskState, reason: str = "CANCELLED") -> TaskState:
        task.status = TaskStatus.CANCELLED
        task.failure_reason = reason
        return task

    def run(
        self,
        objective: str,
        deep_mode: bool = False,
        context: dict[str, Any] | None = None,
    ) -> tuple[TaskState, object | None]:
        if not deep_mode and self.compatibility_mode:
            return self.run_compatibility_mode(objective)

        return self.run_deep_mode(objective, context=context)

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
                if not (task.state == TaskEngineState.REVISE and label == "continue-plan"):
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

    def run_deep_mode(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[TaskState, dict[str, Any] | None]:
        task = self.create_task(
            objective=objective,
            verification_required=True,
            execution_mode="MULTI_STEP",
        )

        if context:
            task.execution_context.derived_values.update(dict(context))

        if not self.advance(task, TaskEngineState.PLAN, label="understand"):
            return task, None

        plan = self._build_plan(task)

        if plan is None:
            return task, None

        task.plan_steps = plan.steps
        task.plan = plan

        return self._drive_task(task)

    def _drive_task(self, task: TaskState) -> tuple[TaskState, dict[str, Any] | None]:
        if task.plan is not None:
            task.plan_steps = task.plan.steps

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
                decision = self._verification_decision(task, verification)

                if decision == "FINISH":
                    task.verification_status = VerificationStatus.PASSED
                    self._mark_remaining_steps_skipped(task)
                    self.advance(task, TaskEngineState.FINISH, label="verify")
                    break

                if decision == "REVISE":
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

            if observation.error_code == APPROVAL_REQUIRED:
                task.status = TaskStatus.AWAITING_APPROVAL
                task.state = TaskEngineState.PLAN
                task.execution_context.awaiting_step_id = pending_step.step_id
                task.execution_context.awaiting_tool_name = pending_step.tool_name
                break

            if observation.error_code == TOOL_DENIED:
                task.status = TaskStatus.BLOCKED
                task.failure_reason = TOOL_DENIED
                break

            if observation.error_code and not observation.requires_revision:
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
                if not self.advance(task, TaskEngineState.REVISE, label="continue-plan"):
                    break

                if not self.advance(task, TaskEngineState.PLAN, label="continue-plan"):
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
            "task_status": task.status.value,
        }

        return task, payload

    def _build_plan(self, task: TaskState) -> TaskPlan | None:
        try:
            raw_plan = self.plan_builder(task.objective, task)
        except Exception:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=PLANNER_FAILURE,
            )
            return None

        if isinstance(raw_plan, dict) and "steps" in raw_plan:
            raw_steps = raw_plan.get("steps") or []
            goal = str(raw_plan.get("goal", task.objective)).strip() or task.objective
            completion_criteria = str(raw_plan.get("completion_criteria", "")).strip()
            failure_policy = str(raw_plan.get("failure_policy", "")).strip()
            maximum_step_count = min(
                int(raw_plan.get("maximum_step_count", self.limits.max_steps)),
                self.limits.max_steps,
            )
            workflow_context = raw_plan.get("workflow_context")
            if isinstance(workflow_context, dict):
                task.execution_context.derived_values["workflow_context"] = dict(workflow_context)

            workflow_policy = raw_plan.get("workflow_policy")
            if isinstance(workflow_policy, dict):
                task.execution_context.derived_values["workflow_policy"] = dict(workflow_policy)
        else:
            raw_steps = raw_plan
            goal = task.objective
            completion_criteria = ""
            failure_policy = ""
            maximum_step_count = self.limits.max_steps

        if not isinstance(raw_steps, list) or not raw_steps:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=INVALID_PLAN,
            )
            return None

        if len(raw_steps) > self.limits.max_steps:
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=STEP_LIMIT_REACHED,
            )
            return None

        plan_steps: list[PlanStep] = []

        for index, raw_step in enumerate(raw_steps, start=1):
            try:
                plan_steps.append(self._coerce_plan_step(raw_step, index))
            except Exception:
                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason=INVALID_PLAN,
                )
                return None

        if self._has_duplicate_plan_steps(plan_steps):
            task.transition_to(
                TaskEngineState.FAILED,
                failure_reason=INVALID_PLAN,
            )
            return None

        task.execution_context.completion_criteria = completion_criteria
        task.execution_context.failure_policy = failure_policy

        return TaskPlan(
            goal=goal,
            steps=plan_steps,
            maximum_step_count=maximum_step_count,
            completion_criteria=completion_criteria,
            failure_policy=failure_policy,
        )

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

    @staticmethod
    def _has_duplicate_plan_steps(plan_steps: list[PlanStep]) -> bool:
        seen_ids: set[int] = set()
        seen_signatures: set[tuple[str, str, str | None]] = set()

        for step in plan_steps:
            signature = (step.action_type.value, step.objective.strip().lower(), step.tool_name)
            if step.step_id in seen_ids or signature in seen_signatures:
                return True
            seen_ids.add(step.step_id)
            seen_signatures.add(signature)

        return False

    def _execute_plan_step(self, task: TaskState, step: PlanStep) -> dict[str, Any]:
        if step.action_type == ActionType.TOOL:
            return self._execute_tool_step(task, step)

        return self._execute_reasoning_step(task, step)

    @staticmethod
    def _normalize_policy_tool_set(raw_values: Any) -> set[str]:
        if raw_values is None:
            return set()

        normalized_values = raw_values
        if isinstance(raw_values, str):
            parsed: Any = raw_values
            try:
                parsed = ast.literal_eval(raw_values)
            except Exception:
                parsed = raw_values

            if isinstance(parsed, (list, tuple, set, frozenset)):
                normalized_values = parsed
            else:
                normalized_values = [raw_values]

        if isinstance(normalized_values, (list, tuple, set, frozenset)):
            return {str(item) for item in normalized_values if str(item).strip()}

        return {str(normalized_values)} if str(normalized_values).strip() else set()

    @staticmethod
    def _record_policy_diagnostics(
        task: TaskState,
        step: PlanStep,
        *,
        policy_decision: str,
        validation_result: str,
        permission_decision: str,
        result_status: str,
        failure_category: str | None,
    ) -> None:
        task.execution_context.derived_values["last_step_diagnostics"] = {
            "task_id": task.task_id,
            "pending_step_id": step.step_id,
            "tool_name": step.tool_name,
            "workflow_type": task.execution_context.derived_values.get("workflow_type"),
            "workflow_policy_decision": policy_decision,
            "approval_validation_result": validation_result,
            "permission_decision": permission_decision,
            "resulting_task_status": result_status,
            "sanitized_failure_category": failure_category,
        }

    def _execute_tool_step(self, task: TaskState, step: PlanStep) -> dict[str, Any]:
        workflow_policy = task.execution_context.derived_values.get("workflow_policy")
        if isinstance(workflow_policy, dict):
            allowed_tools = self._normalize_policy_tool_set(workflow_policy.get("allowed_tools"))
            forbidden_tools = self._normalize_policy_tool_set(workflow_policy.get("forbidden_tools"))
            if step.tool_name in forbidden_tools or (allowed_tools and step.tool_name not in allowed_tools):
                step.status = PlanStepStatus.FAILED
                step.error = TOOL_DENIED
                self._record_policy_diagnostics(
                    task,
                    step,
                    policy_decision="DENY",
                    validation_result="NOT_EVALUATED",
                    permission_decision="DENY",
                    result_status=TaskStatus.BLOCKED.value,
                    failure_category=TOOL_DENIED,
                )
                return {
                    "status": "FAILED",
                    "result_available": False,
                    "evidence_available": False,
                    "error_code": TOOL_DENIED,
                    "recoverable": False,
                }

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

        resolved_args = self._resolve_tool_args(task, step)

        if resolved_args is None:
            step.status = PlanStepStatus.FAILED
            step.error = TOOL_EXECUTION_FAILED

            return {
                "status": "FAILED",
                "result_available": False,
                "evidence_available": False,
                "error_code": TOOL_EXECUTION_FAILED,
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

        if hasattr(self.runtime, "execute_tool_step"):
            runtime_result = self.runtime.execute_tool_step(
                step.tool_name,
                resolved_args,
                conversation_id=task.task_id,
                request_id=f"{task.task_id}:{step.step_id}:{step.retry_count}",
                approval_token=task.execution_context.approval_token,
                approval_scope=f"{task.task_id}:{step.step_id}",
                reason=f"Execute planned step {step.step_id}.",
            )
        else:
            runtime_result = self.runtime.run(step.objective)
        tool_status = getattr(runtime_result, "tool_status", None)
        result_status = getattr(runtime_result, "status", None)
        tool_name = getattr(runtime_result, "tool_name", step.tool_name)
        output = getattr(runtime_result, "output", None)
        permission_decision = str(getattr(runtime_result, "decision", "UNKNOWN") or "UNKNOWN")
        approval_state = str(getattr(runtime_result, "approval_state", "unknown") or "unknown")
        error_category = getattr(runtime_result, "error_category", None)

        step.result_summary = (
            f"status={result_status};"
            f"tool={tool_name};"
            f"tool_status={tool_status}"
        )

        if result_status != "TOOL_RESULT" or tool_name != step.tool_name:
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
            if output is None or not isinstance(output, dict):
                step.status = PlanStepStatus.FAILED
                step.error = "MALFORMED_TOOL_RESULT"

                return {
                    "status": "FAILED",
                    "result_available": False,
                    "evidence_available": False,
                    "error_code": "MALFORMED_TOOL_RESULT",
                    "recoverable": False,
                }

            step.status = PlanStepStatus.EXECUTED
            sanitized_output = self._sanitize_step_output(output)
            self._record_step_result(
                task,
                StepResult(
                    step_id=step.step_id,
                    status="EXECUTED",
                    tool_name=tool_name,
                    sanitized_output=sanitized_output,
                    result_summary=step.result_summary,
                    retry_count=step.retry_count,
                ),
            )
            task.execution_context.approval_token = None
            self._record_policy_diagnostics(
                task,
                step,
                policy_decision="ALLOW",
                validation_result="VALID" if approval_state == "approved" else "NOT_REQUIRED",
                permission_decision=permission_decision,
                result_status=TaskStatus.RUNNING.value,
                failure_category=None,
            )

            return {
                "status": "EXECUTED",
                "result_available": True,
                "evidence_available": True,
                "error_code": None,
                "recoverable": False,
            }

        if tool_status == "AWAITING_APPROVAL":
            step.status = PlanStepStatus.PENDING
            step.error = None
            self._record_policy_diagnostics(
                task,
                step,
                policy_decision="ALLOW",
                validation_result="PENDING",
                permission_decision=permission_decision,
                result_status=TaskStatus.AWAITING_APPROVAL.value,
                failure_category=APPROVAL_REQUIRED,
            )

            return {
                "status": "AWAITING_APPROVAL",
                "result_available": False,
                "evidence_available": False,
                "error_code": APPROVAL_REQUIRED,
                "recoverable": False,
            }

        if tool_status == "DENIED":
            step.status = PlanStepStatus.FAILED
            step.error = TOOL_DENIED
            self._record_policy_diagnostics(
                task,
                step,
                policy_decision="DENY",
                validation_result="INVALID" if error_category == "invalid_approval" else "NOT_REQUIRED",
                permission_decision=permission_decision,
                result_status=TaskStatus.BLOCKED.value,
                failure_category=TOOL_DENIED,
            )

            return {
                "status": "FAILED",
                "result_available": False,
                "evidence_available": False,
                "error_code": TOOL_DENIED,
                "recoverable": False,
            }

        step.status = PlanStepStatus.FAILED
        step.error = TOOL_EXECUTION_FAILED
        self._record_policy_diagnostics(
            task,
            step,
            policy_decision="ALLOW",
            validation_result="INVALID" if error_category == "invalid_approval" else "NOT_REQUIRED",
            permission_decision=permission_decision,
            result_status=TaskStatus.FAILED.value,
            failure_category=TOOL_EXECUTION_FAILED,
        )
        self._record_step_result(
            task,
            StepResult(
                step_id=step.step_id,
                status="FAILED",
                tool_name=tool_name,
                result_summary=step.result_summary,
                failure_category=TOOL_EXECUTION_FAILED,
                retry_count=step.retry_count,
            ),
        )

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
            self._record_step_result(
                task,
                StepResult(
                    step_id=step.step_id,
                    status="EXECUTED",
                    result_summary=summary,
                    retry_count=step.retry_count,
                ),
            )

            return {
                "status": "EXECUTED",
                "result_available": True,
                "evidence_available": bool(result.get("evidence", False)),
                "error_code": None,
                "recoverable": False,
            }

        step.status = PlanStepStatus.FAILED
        step.error = result.get("error_code", REASONING_OPERATION_FAILED)
        self._record_step_result(
            task,
            StepResult(
                step_id=step.step_id,
                status="FAILED",
                result_summary=summary or None,
                failure_category=step.error,
                retry_count=step.retry_count,
            ),
        )

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
            if failed_step.retry_count >= task.execution_context.retry_budget_per_step:
                task.transition_to(
                    TaskEngineState.FAILED,
                    failure_reason=failed_step.error or reason or REASONING_OPERATION_FAILED,
                )
                return

            failed_step.retry_count += 1
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
                issues=(VerificationIssue.VERIFICATION_UNAVAILABLE,),
                summary="Verifier raised an exception.",
            )

        task.verification_report = self._extract_verification_report(result)

        coerced = self._coerce_verification_result(result)

        if coerced is None:
            return VerificationResult(
                outcome=VerificationOutcome.FAIL,
                issues=(VerificationIssue.UNSUPPORTED_OUTPUT,),
                summary="Verifier returned an unsupported structure.",
            )

        return coerced

    @staticmethod
    def _verification_decision(task: TaskState, verification: VerificationResult) -> str:
        report = task.verification_report or {}
        action = str(report.get("recommended_action", "")).upper()

        if verification.outcome == VerificationOutcome.PASS:
            if action in ("", "FINISH"):
                return "FINISH"
            return "FAIL"

        if verification.outcome == VerificationOutcome.CORRECTABLE:
            if action in ("", "REVISE"):
                return "REVISE"
            return "FAIL"

        if verification.outcome == VerificationOutcome.FAIL:
            return "FAIL"

        return "FAIL"

    @staticmethod
    def _extract_verification_report(result: Any) -> dict[str, Any] | None:
        to_public = getattr(result, "to_public_dict", None)

        if callable(to_public):
            try:
                return to_public()
            except Exception:
                return None

        if isinstance(result, dict):
            return result

        outcome = getattr(result, "outcome", None)

        if outcome is None:
            return None

        report = {
            "outcome": str(getattr(outcome, "value", outcome)),
            "issues": [
                str(getattr(item, "value", item))
                for item in getattr(result, "issues", ())
            ],
            "confidence": getattr(result, "confidence", None),
            "recommended_action": str(
                getattr(
                    getattr(result, "recommended_action", None),
                    "value",
                    getattr(result, "recommended_action", ""),
                )
            ),
            "summary": str(getattr(result, "summary", "")),
        }

        return report

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
        lowered = step.objective.lower().strip()

        if "prepare a calculator expression" in lowered:
            health_result = TaskEngine._latest_step_output(task, "system.health") or {}
            connection_keys = ("ollama_connected", "database_connected", "local_model_available")
            total = len(connection_keys)
            connected = sum(1 for key in connection_keys if bool(health_result.get(key)))
            task.execution_context.derived_values["service_connection_expression"] = f"({connected} / {total}) * 100"
            task.execution_context.derived_values["service_connection_connected"] = connected
            task.execution_context.derived_values["service_connection_total"] = total

            return {
                "status": "EXECUTED",
                "summary": f"Prepared calculator expression using {connected} connected services out of {total}.",
                "evidence": True,
            }

        if "compose the final answer" in lowered:
            health_result = TaskEngine._latest_step_output(task, "system.health") or {}
            calculator_result = TaskEngine._latest_step_output(task, "calculator") or {}
            percentage = calculator_result.get("result")
            if percentage is None:
                return {
                    "status": "FAILED",
                    "summary": "",
                    "error_code": "MISSING_RESULT",
                    "recoverable": False,
                }

            connected = task.execution_context.derived_values.get("service_connection_connected", 0)
            total = task.execution_context.derived_values.get("service_connection_total", 0)

            return {
                "status": "EXECUTED",
                "summary": (
                    f"SHY has {connected} of {total} required services connected "
                    f"({float(percentage):g}%). Database connected={bool(health_result.get('database_connected'))}; "
                    f"Ollama connected={bool(health_result.get('ollama_connected'))}; "
                    f"Local model available={bool(health_result.get('local_model_available'))}."
                ),
                "evidence": True,
            }

        return {
            "status": "EXECUTED",
            "summary": f"Completed reasoning step {step.step_id}: {step.objective}",
            "evidence": False,
        }

    @staticmethod
    def _sanitize_step_output(output: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in output.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("password", "secret", "token", "key", "reasoning", "chain", "debug")):
                continue
            sanitized[str(key)] = value
        return sanitized

    @staticmethod
    def _record_step_result(task: TaskState, step_result: StepResult):
        task.execution_context.step_results = [
            item for item in task.execution_context.step_results if item.step_id != step_result.step_id
        ]
        task.execution_context.step_results.append(step_result)

    @staticmethod
    def _latest_step_output(task: TaskState, tool_name: str) -> dict[str, Any] | None:
        for result in reversed(task.execution_context.step_results):
            if result.tool_name == tool_name and isinstance(result.sanitized_output, dict):
                return result.sanitized_output
        return None

    @staticmethod
    def _resolve_tool_args(task: TaskState, step: PlanStep) -> dict[str, Any] | None:
        if not step.tool_args:
            return {}

        resolved: dict[str, Any] = {}
        for key, value in step.tool_args.items():
            if key.endswith("_context_key"):
                target_key = key[: -len("_context_key")]
                context_value = task.execution_context.derived_values.get(str(value))
                if context_value is None:
                    return None
                resolved[target_key] = context_value
                continue
            resolved[key] = value

        return resolved

    def _default_verifier(self, task: TaskState):
        return verifier_module.verify_task_result(
            task,
            semantic_verifier=self.semantic_verifier,
        )
