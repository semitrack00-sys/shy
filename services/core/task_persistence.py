import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from memory import connect

try:
    from agent_runtime.loop_state import (
        ActionType,
        PlanStep,
        PlanStepStatus,
        StepObservation,
        StepResult,
        TaskEngineState,
        TaskExecutionContext,
        TaskPlan,
        TaskState,
        TaskStatus,
        VerificationOutcome,
        VerificationResult,
        VerificationStatus,
    )
except ModuleNotFoundError:
    # The importing module is responsible for loading agent_runtime for fallback paths.
    raise


class TaskPersistenceError(RuntimeError):
    pass


class TaskNotFoundError(TaskPersistenceError):
    pass


class StaleTaskVersionError(TaskPersistenceError):
    pass


class TaskLockError(TaskPersistenceError):
    pass


class TaskMalformedStateError(TaskPersistenceError):
    pass


@dataclass(frozen=True)
class PersistedTaskSnapshot:
    task: TaskState
    revision: int
    conversation_id: str
    execution_mode: str
    created_at: datetime | None
    updated_at: datetime | None
    completed_at: datetime | None


SENSITIVE_KEY_TOKENS = (
    "password",
    "secret",
    "token",
    "key",
    "api_key",
    "authorization",
    "cookie",
    "database_url",
    "env",
    "prompt",
    "reasoning",
    "thought",
    "chain",
)


def _sanitize_storage_value(value: Any, max_chars: int = 4000) -> Any:
    if value is None:
        return None

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(token in lowered for token in SENSITIVE_KEY_TOKENS):
                continue
            cleaned[key_text] = _sanitize_storage_value(item, max_chars=max_chars)
        return cleaned

    if isinstance(value, list):
        return [_sanitize_storage_value(item, max_chars=max_chars) for item in value[:40]]

    if isinstance(value, (tuple, set, frozenset)):
        normalized = list(value)
        return [_sanitize_storage_value(item, max_chars=max_chars) for item in normalized[:40]]

    if isinstance(value, str):
        text = " ".join(value.split())
        if len(text) > max_chars:
            return text[: max_chars - 3].rstrip() + "..."
        return text

    if isinstance(value, (int, float, bool)):
        return value

    return _sanitize_storage_value(str(value), max_chars=max_chars)


def _serialize_verification_result(verification_result: VerificationResult | None) -> dict[str, Any] | None:
    if verification_result is None:
        return None

    return {
        "outcome": verification_result.outcome.value,
        "issues": [issue.value for issue in verification_result.issues],
        "summary": verification_result.summary,
    }


def _deserialize_verification_result_safe(payload: dict[str, Any] | None) -> VerificationResult | None:
    if payload is None:
        return None

    try:
        outcome = VerificationOutcome(str(payload.get("outcome", VerificationOutcome.FAIL.value)))
    except Exception as exc:
        raise TaskMalformedStateError("Invalid verification outcome.") from exc

    raw_issues = payload.get("issues", [])
    issues = []
    try:
        from agent_runtime.loop_state import VerificationIssue

        for issue in raw_issues:
            issues.append(VerificationIssue(str(issue)))
    except Exception as exc:
        raise TaskMalformedStateError("Invalid verification issues.") from exc

    return VerificationResult(
        outcome=outcome,
        issues=tuple(issues),
        summary=str(payload.get("summary", "")),
    )


def _serialize_task_state(task: TaskState) -> dict[str, Any]:
    payload = {
        "state": task.state.value,
        "objective": task.objective,
        "current_step": task.current_step,
        "iteration_count": task.iteration_count,
        "tool_call_count": task.tool_call_count,
        "started_at": task.started_at,
        "started_monotonic": task.started_monotonic,
        "failure_reason": task.failure_reason,
        "verification_status": task.verification_status.value,
        "verification_result": _serialize_verification_result(task.verification_result),
        "verification_report": _sanitize_storage_value(task.verification_report),
        "capabilities": list(task.capabilities),
        "steps": [
            {
                "index": step.index,
                "state": step.state.value,
                "label": step.label,
                "result_status": step.result_status,
                "tool_name": step.tool_name,
            }
            for step in task.steps
        ],
        "plan": (
            {
                "goal": task.plan.goal,
                "maximum_step_count": task.plan.maximum_step_count,
                "current_step": task.plan.current_step,
                "completion_criteria": task.plan.completion_criteria,
                "failure_policy": task.plan.failure_policy,
            }
            if task.plan is not None
            else None
        ),
        "plan_steps": [
            {
                "step_id": step.step_id,
                "action_type": step.action_type.value,
                "objective": step.objective,
                "status": step.status.value,
                "tool_name": step.tool_name,
                "tool_args": _sanitize_storage_value(step.tool_args),
                "result_summary": _sanitize_storage_value(step.result_summary),
                "error": step.error,
                "retry_count": step.retry_count,
            }
            for step in task.plan_steps
        ],
        "observations": [
            {
                "step_id": item.step_id,
                "status": item.status,
                "result_available": item.result_available,
                "evidence_available": item.evidence_available,
                "error_code": item.error_code,
                "requires_revision": item.requires_revision,
            }
            for item in task.observations
        ],
        "execution_context": {
            "mode": task.execution_context.mode,
            "max_steps": task.execution_context.max_steps,
            "hard_max_steps": task.execution_context.hard_max_steps,
            "completion_criteria": task.execution_context.completion_criteria,
            "failure_policy": task.execution_context.failure_policy,
            "retry_budget_per_step": task.execution_context.retry_budget_per_step,
            "derived_values": _sanitize_storage_value(task.execution_context.derived_values),
            "awaiting_step_id": task.execution_context.awaiting_step_id,
            "awaiting_tool_name": task.execution_context.awaiting_tool_name,
        },
    }

    return _sanitize_storage_value(payload)


def _deserialize_task_state(task_id: str, status_text: str, payload: dict[str, Any], step_rows: list[dict[str, Any]]) -> TaskState:
    try:
        state = TaskEngineState(str(payload.get("state", TaskEngineState.UNDERSTAND.value)))
        verification_status = VerificationStatus(
            str(payload.get("verification_status", VerificationStatus.NOT_REQUIRED.value))
        )
        task_status = TaskStatus(str(status_text))
    except Exception as exc:
        raise TaskMalformedStateError("Task row contains invalid state enums.") from exc

    execution_context_payload = payload.get("execution_context", {})
    try:
        execution_context = TaskExecutionContext(
            mode=str(execution_context_payload.get("mode", "MULTI_STEP")),
            max_steps=int(execution_context_payload.get("max_steps", 5)),
            hard_max_steps=int(execution_context_payload.get("hard_max_steps", 8)),
            completion_criteria=str(execution_context_payload.get("completion_criteria", "")),
            failure_policy=str(execution_context_payload.get("failure_policy", "")),
            retry_budget_per_step=int(execution_context_payload.get("retry_budget_per_step", 1)),
            step_results=[],
            derived_values=dict(execution_context_payload.get("derived_values") or {}),
            awaiting_step_id=execution_context_payload.get("awaiting_step_id"),
            awaiting_tool_name=execution_context_payload.get("awaiting_tool_name"),
            approval_token=None,
        )
    except Exception as exc:
        raise TaskMalformedStateError("Task execution context is malformed.") from exc

    plan_steps_payload = payload.get("plan_steps", [])
    plan_steps: list[PlanStep] = []
    try:
        for row in plan_steps_payload:
            plan_steps.append(
                PlanStep(
                    step_id=int(row.get("step_id")),
                    action_type=ActionType(str(row.get("action_type"))),
                    objective=str(row.get("objective", "")).strip(),
                    status=PlanStepStatus(str(row.get("status", PlanStepStatus.PENDING.value))),
                    tool_name=row.get("tool_name"),
                    tool_args=row.get("tool_args"),
                    result_summary=row.get("result_summary"),
                    error=row.get("error"),
                    retry_count=int(row.get("retry_count", 0)),
                )
            )
    except Exception as exc:
        raise TaskMalformedStateError("Task plan steps are malformed.") from exc

    observations_payload = payload.get("observations", [])
    observations: list[StepObservation] = []
    try:
        for row in observations_payload:
            observations.append(
                StepObservation(
                    step_id=int(row.get("step_id")),
                    status=str(row.get("status", "FAILED")),
                    result_available=bool(row.get("result_available", False)),
                    evidence_available=bool(row.get("evidence_available", False)),
                    error_code=row.get("error_code"),
                    requires_revision=bool(row.get("requires_revision", False)),
                )
            )
    except Exception as exc:
        raise TaskMalformedStateError("Task observations are malformed.") from exc

    step_results: list[StepResult] = []
    try:
        for row in step_rows:
            step_results.append(
                StepResult(
                    step_id=int(row["step_id"]),
                    status=str(row.get("public_status", "FAILED")),
                    tool_name=row.get("tool_name"),
                    sanitized_output=(row.get("step_payload") or {}).get("sanitized_output"),
                    result_summary=row.get("result_summary"),
                    failure_category=row.get("failure_category"),
                    retry_count=int(row.get("retry_count", 0)),
                )
            )
    except Exception as exc:
        raise TaskMalformedStateError("Task step rows are malformed.") from exc

    execution_context.step_results = step_results

    verification_result = _deserialize_verification_result_safe(payload.get("verification_result"))

    plan_payload = payload.get("plan")
    plan = None
    if plan_payload is not None:
        try:
            plan = TaskPlan(
                goal=str(plan_payload.get("goal", payload.get("objective", ""))).strip(),
                steps=plan_steps,
                maximum_step_count=int(plan_payload.get("maximum_step_count", execution_context.max_steps)),
                current_step=int(plan_payload.get("current_step", 0)),
                completion_criteria=str(plan_payload.get("completion_criteria", execution_context.completion_criteria)),
                failure_policy=str(plan_payload.get("failure_policy", execution_context.failure_policy)),
            )
        except Exception as exc:
            raise TaskMalformedStateError("Task plan payload is malformed.") from exc

    task = TaskState(
        task_id=task_id,
        objective=str(payload.get("objective", "")).strip(),
        state=state,
        steps=[],
        plan_steps=plan_steps,
        observations=observations,
        capabilities=tuple(payload.get("capabilities") or ()),
        current_step=payload.get("current_step"),
        iteration_count=int(payload.get("iteration_count", 0)),
        tool_call_count=int(payload.get("tool_call_count", 0)),
        started_at=float(payload.get("started_at", time.time())),
        started_monotonic=float(payload.get("started_monotonic", time.monotonic())),
        status=task_status,
        verification_status=verification_status,
        verification_result=verification_result,
        verification_report=payload.get("verification_report"),
        failure_reason=payload.get("failure_reason"),
        plan=plan,
        execution_context=execution_context,
    )

    steps_payload = payload.get("steps", [])
    try:
        from agent_runtime.loop_state import TaskStepArtifact

        task.steps = [
            TaskStepArtifact(
                index=int(item.get("index", 0)),
                state=TaskEngineState(str(item.get("state", TaskEngineState.UNDERSTAND.value))),
                label=str(item.get("label", "")),
                result_status=item.get("result_status"),
                tool_name=item.get("tool_name"),
            )
            for item in steps_payload
        ]
    except Exception as exc:
        raise TaskMalformedStateError("Task artifacts are malformed.") from exc

    return task


def _task_public_status(task: TaskState) -> str:
    return task.status.value


def _task_current_step(task: TaskState) -> int | None:
    for step in task.plan_steps:
        if step.status == PlanStepStatus.PENDING:
            return step.step_id
    return None


def _task_retry_total(task: TaskState) -> int:
    return sum(int(step.retry_count or 0) for step in task.plan_steps)


def _task_approval_state(task: TaskState) -> str:
    if task.status == TaskStatus.AWAITING_APPROVAL:
        return "AWAITING_APPROVAL"
    return "NOT_REQUIRED"


def _task_completed_at(task: TaskState) -> datetime | None:
    if task.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED, TaskStatus.BLOCKED}:
        return datetime.utcnow()
    return None


class PostgresTaskRepository:
    def ensure_schema(self) -> None:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS task_runs (
                        task_id TEXT PRIMARY KEY,
                        conversation_id UUID NOT NULL,
                        goal TEXT NOT NULL,
                        public_status TEXT NOT NULL,
                        execution_mode TEXT NOT NULL,
                        current_step INTEGER,
                        completion_criteria TEXT NOT NULL DEFAULT '',
                        failure_policy TEXT NOT NULL DEFAULT '',
                        retry_total INTEGER NOT NULL DEFAULT 0,
                        approval_state TEXT NOT NULL DEFAULT 'NOT_REQUIRED',
                        awaiting_step_id INTEGER,
                        awaiting_tool_name TEXT,
                        revision INTEGER NOT NULL DEFAULT 1,
                        task_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        completed_at TIMESTAMPTZ
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS task_run_steps (
                        id BIGSERIAL PRIMARY KEY,
                        task_id TEXT NOT NULL REFERENCES task_runs(task_id) ON DELETE CASCADE,
                        step_id INTEGER NOT NULL,
                        tool_name TEXT,
                        public_status TEXT NOT NULL,
                        result_summary TEXT,
                        failure_category TEXT,
                        retry_count INTEGER NOT NULL DEFAULT 0,
                        step_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE(task_id, step_id)
                    )
                    """
                )

    @contextmanager
    def task_lock(self, task_id: str):
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked", (str(task_id),))
                row = cur.fetchone()
                if not row or not bool(row.get("locked")):
                    raise TaskLockError("Task is currently being processed.")

            try:
                yield
            finally:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (str(task_id),))

    def create_task(self, task: TaskState, conversation_id: str, execution_mode: str) -> int:
        payload = _serialize_task_state(task)
        completed_at = _task_completed_at(task)

        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO task_runs (
                        task_id,
                        conversation_id,
                        goal,
                        public_status,
                        execution_mode,
                        current_step,
                        completion_criteria,
                        failure_policy,
                        retry_total,
                        approval_state,
                        awaiting_step_id,
                        awaiting_tool_name,
                        revision,
                        task_payload,
                        completed_at
                    )
                    VALUES (%s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s::jsonb, %s)
                    ON CONFLICT (task_id) DO NOTHING
                    """,
                    (
                        task.task_id,
                        str(conversation_id),
                        task.objective,
                        _task_public_status(task),
                        execution_mode,
                        _task_current_step(task),
                        task.execution_context.completion_criteria,
                        task.execution_context.failure_policy,
                        _task_retry_total(task),
                        _task_approval_state(task),
                        task.execution_context.awaiting_step_id,
                        task.execution_context.awaiting_tool_name,
                        json.dumps(payload),
                        completed_at,
                    ),
                )
                if cur.rowcount != 1:
                    raise StaleTaskVersionError("Task already exists.")

        self._save_steps(task)
        return 1

    def save_task(self, task: TaskState, conversation_id: str, execution_mode: str, expected_revision: int) -> int:
        payload = _serialize_task_state(task)
        completed_at = _task_completed_at(task)

        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE task_runs
                    SET
                        goal = %s,
                        public_status = %s,
                        execution_mode = %s,
                        current_step = %s,
                        completion_criteria = %s,
                        failure_policy = %s,
                        retry_total = %s,
                        approval_state = %s,
                        awaiting_step_id = %s,
                        awaiting_tool_name = %s,
                        task_payload = %s::jsonb,
                        updated_at = NOW(),
                        completed_at = %s,
                        revision = revision + 1
                    WHERE task_id = %s
                      AND conversation_id = %s::uuid
                      AND revision = %s
                    """,
                    (
                        task.objective,
                        _task_public_status(task),
                        execution_mode,
                        _task_current_step(task),
                        task.execution_context.completion_criteria,
                        task.execution_context.failure_policy,
                        _task_retry_total(task),
                        _task_approval_state(task),
                        task.execution_context.awaiting_step_id,
                        task.execution_context.awaiting_tool_name,
                        json.dumps(payload),
                        completed_at,
                        task.task_id,
                        str(conversation_id),
                        int(expected_revision),
                    ),
                )
                if cur.rowcount != 1:
                    raise StaleTaskVersionError("Task version is stale.")

        self._save_steps(task)
        return int(expected_revision) + 1

    def load_task(self, task_id: str) -> PersistedTaskSnapshot | None:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        task_id,
                        conversation_id::text AS conversation_id,
                        public_status,
                        execution_mode,
                        revision,
                        task_payload,
                        created_at,
                        updated_at,
                        completed_at
                    FROM task_runs
                    WHERE task_id = %s
                    """,
                    (str(task_id),),
                )
                row = cur.fetchone()

                if row is None:
                    return None

                cur.execute(
                    """
                    SELECT
                        step_id,
                        tool_name,
                        public_status,
                        result_summary,
                        failure_category,
                        retry_count,
                        step_payload,
                        created_at,
                        updated_at
                    FROM task_run_steps
                    WHERE task_id = %s
                    ORDER BY step_id ASC
                    """,
                    (str(task_id),),
                )
                step_rows = cur.fetchall() or []

        payload = row.get("task_payload") or {}
        if not isinstance(payload, dict):
            raise TaskMalformedStateError("Task payload is not a JSON object.")

        task = _deserialize_task_state(
            task_id=str(row["task_id"]),
            status_text=str(row["public_status"]),
            payload=payload,
            step_rows=step_rows,
        )

        return PersistedTaskSnapshot(
            task=task,
            revision=int(row["revision"]),
            conversation_id=str(row["conversation_id"]),
            execution_mode=str(row["execution_mode"]),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            completed_at=row.get("completed_at"),
        )

    def update_task_status(
        self,
        task_id: str,
        conversation_id: str,
        public_status: str,
        expected_revision: int,
        failure_reason: str | None = None,
    ) -> int:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE task_runs
                    SET
                        public_status = %s,
                        approval_state = CASE WHEN %s = 'AWAITING_APPROVAL' THEN 'AWAITING_APPROVAL' ELSE 'NOT_REQUIRED' END,
                        updated_at = NOW(),
                        completed_at = CASE WHEN %s IN ('COMPLETED', 'CANCELLED', 'FAILED', 'BLOCKED') THEN NOW() ELSE completed_at END,
                        revision = revision + 1,
                        task_payload = jsonb_set(
                            jsonb_set(task_payload, '{failure_reason}', to_jsonb(%s::text), true),
                            '{status}',
                            to_jsonb(%s::text),
                            true
                        )
                    WHERE task_id = %s
                      AND conversation_id = %s::uuid
                      AND revision = %s
                    """,
                    (
                        public_status,
                        public_status,
                        public_status,
                        failure_reason,
                        public_status,
                        str(task_id),
                        str(conversation_id),
                        int(expected_revision),
                    ),
                )
                if cur.rowcount != 1:
                    raise StaleTaskVersionError("Task version is stale.")

        return int(expected_revision) + 1

    def cancel_task(self, task: TaskState, conversation_id: str, expected_revision: int) -> int:
        task.status = TaskStatus.CANCELLED
        task.failure_reason = task.failure_reason or "CANCELLED"
        return self.save_task(
            task=task,
            conversation_id=conversation_id,
            execution_mode=task.execution_context.mode or "MULTI_STEP",
            expected_revision=expected_revision,
        )

    def _save_steps(self, task: TaskState) -> None:
        step_index = {result.step_id: result for result in task.execution_context.step_results}

        with connect() as conn:
            with conn.cursor() as cur:
                for plan_step in task.plan_steps:
                    step_result = step_index.get(plan_step.step_id)
                    tool_name = plan_step.tool_name or (step_result.tool_name if step_result else None)
                    result_summary = (
                        step_result.result_summary
                        if step_result and step_result.result_summary is not None
                        else plan_step.result_summary
                    )
                    failure_category = (
                        step_result.failure_category
                        if step_result and step_result.failure_category is not None
                        else plan_step.error
                    )
                    retry_count = max(
                        int(plan_step.retry_count or 0),
                        int(step_result.retry_count or 0) if step_result else 0,
                    )

                    step_payload = {
                        "action_type": plan_step.action_type.value,
                        "objective": plan_step.objective,
                        "tool_args": _sanitize_storage_value(plan_step.tool_args),
                        "sanitized_output": _sanitize_storage_value(step_result.sanitized_output) if step_result else None,
                    }

                    cur.execute(
                        """
                        INSERT INTO task_run_steps (
                            task_id,
                            step_id,
                            tool_name,
                            public_status,
                            result_summary,
                            failure_category,
                            retry_count,
                            step_payload
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (task_id, step_id)
                        DO UPDATE SET
                            tool_name = EXCLUDED.tool_name,
                            public_status = EXCLUDED.public_status,
                            result_summary = EXCLUDED.result_summary,
                            failure_category = EXCLUDED.failure_category,
                            retry_count = EXCLUDED.retry_count,
                            step_payload = EXCLUDED.step_payload,
                            updated_at = NOW()
                        """,
                        (
                            task.task_id,
                            int(plan_step.step_id),
                            tool_name,
                            plan_step.status.value,
                            _sanitize_storage_value(result_summary),
                            failure_category,
                            retry_count,
                            json.dumps(_sanitize_storage_value(step_payload)),
                        ),
                    )


class InMemoryTaskRepository:
    """Deterministic test fallback. Not used in production unless explicitly injected."""

    def __init__(self):
        self._tasks: dict[str, dict[str, Any]] = {}
        self._steps: dict[str, list[dict[str, Any]]] = {}
        self._locks: dict[str, threading.Lock] = {}

    def ensure_schema(self) -> None:
        return None

    @contextmanager
    def task_lock(self, task_id: str):
        lock = self._locks.setdefault(str(task_id), threading.Lock())
        if not lock.acquire(blocking=False):
            raise TaskLockError("Task is currently being processed.")
        try:
            yield
        finally:
            lock.release()

    def create_task(self, task: TaskState, conversation_id: str, execution_mode: str) -> int:
        task_id = str(task.task_id)
        if task_id in self._tasks:
            raise StaleTaskVersionError("Task already exists.")

        self._tasks[task_id] = {
            "task_id": task_id,
            "conversation_id": str(conversation_id),
            "public_status": task.status.value,
            "execution_mode": str(execution_mode),
            "revision": 1,
            "task_payload": _serialize_task_state(task),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "completed_at": _task_completed_at(task),
        }
        self._save_steps(task)
        return 1

    def save_task(self, task: TaskState, conversation_id: str, execution_mode: str, expected_revision: int) -> int:
        task_id = str(task.task_id)
        row = self._tasks.get(task_id)
        if row is None:
            raise TaskNotFoundError("Task not found.")
        if row["revision"] != int(expected_revision):
            raise StaleTaskVersionError("Task version is stale.")
        if row["conversation_id"] != str(conversation_id):
            raise StaleTaskVersionError("Conversation mismatch for task persistence.")

        row["public_status"] = task.status.value
        row["execution_mode"] = str(execution_mode)
        row["task_payload"] = _serialize_task_state(task)
        row["revision"] = int(row["revision"]) + 1
        row["updated_at"] = datetime.utcnow()
        row["completed_at"] = _task_completed_at(task)
        self._save_steps(task)
        return int(row["revision"])

    def load_task(self, task_id: str) -> PersistedTaskSnapshot | None:
        row = self._tasks.get(str(task_id))
        if row is None:
            return None

        payload = row.get("task_payload") or {}
        if not isinstance(payload, dict):
            raise TaskMalformedStateError("Task payload is malformed.")

        step_rows = self._steps.get(str(task_id), [])
        task = _deserialize_task_state(
            task_id=str(row["task_id"]),
            status_text=str(row["public_status"]),
            payload=payload,
            step_rows=step_rows,
        )
        return PersistedTaskSnapshot(
            task=task,
            revision=int(row["revision"]),
            conversation_id=str(row["conversation_id"]),
            execution_mode=str(row["execution_mode"]),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            completed_at=row.get("completed_at"),
        )

    def update_task_status(
        self,
        task_id: str,
        conversation_id: str,
        public_status: str,
        expected_revision: int,
        failure_reason: str | None = None,
    ) -> int:
        snapshot = self.load_task(task_id)
        if snapshot is None:
            raise TaskNotFoundError("Task not found.")

        if snapshot.revision != int(expected_revision):
            raise StaleTaskVersionError("Task version is stale.")

        if snapshot.conversation_id != str(conversation_id):
            raise StaleTaskVersionError("Conversation mismatch for task persistence.")

        task = snapshot.task
        task.status = TaskStatus(public_status)
        task.failure_reason = failure_reason

        return self.save_task(
            task=task,
            conversation_id=conversation_id,
            execution_mode=snapshot.execution_mode,
            expected_revision=expected_revision,
        )

    def cancel_task(self, task: TaskState, conversation_id: str, expected_revision: int) -> int:
        task.status = TaskStatus.CANCELLED
        task.failure_reason = task.failure_reason or "CANCELLED"
        return self.save_task(
            task=task,
            conversation_id=conversation_id,
            execution_mode=task.execution_context.mode or "MULTI_STEP",
            expected_revision=expected_revision,
        )

    def _save_steps(self, task: TaskState) -> None:
        by_step = {item.step_id: item for item in task.execution_context.step_results}
        rows: list[dict[str, Any]] = []

        for step in task.plan_steps:
            step_result = by_step.get(step.step_id)
            rows.append(
                {
                    "step_id": int(step.step_id),
                    "tool_name": step.tool_name or (step_result.tool_name if step_result else None),
                    "public_status": step.status.value,
                    "result_summary": _sanitize_storage_value(
                        step_result.result_summary if step_result and step_result.result_summary is not None else step.result_summary
                    ),
                    "failure_category": (
                        step_result.failure_category if step_result and step_result.failure_category is not None else step.error
                    ),
                    "retry_count": max(
                        int(step.retry_count or 0),
                        int(step_result.retry_count or 0) if step_result else 0,
                    ),
                    "step_payload": {
                        "action_type": step.action_type.value,
                        "objective": step.objective,
                        "tool_args": _sanitize_storage_value(step.tool_args),
                        "sanitized_output": _sanitize_storage_value(step_result.sanitized_output) if step_result else None,
                    },
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            )

        self._steps[str(task.task_id)] = rows

    # Test-only helper for corruption checks.
    def corrupt_task_payload(self, task_id: str, payload: Any) -> None:
        if str(task_id) not in self._tasks:
            raise TaskNotFoundError("Task not found.")
        self._tasks[str(task_id)]["task_payload"] = payload

    # Test-only helper for asserting no token persistence.
    def debug_raw_task_payload(self, task_id: str) -> dict[str, Any] | None:
        row = self._tasks.get(str(task_id))
        if row is None:
            return None
        return row.get("task_payload")
