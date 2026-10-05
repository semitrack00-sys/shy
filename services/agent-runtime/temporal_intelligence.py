from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Sequence


class TemporalBoundary(str, Enum):
    READY = "READY"
    TIMEZONE_REQUIRED = "TIMEZONE_REQUIRED"
    INVALID_WINDOW = "INVALID_WINDOW"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    DEADLINE_CONFLICT = "DEADLINE_CONFLICT"
    NO_TASKS = "NO_TASKS"


@dataclass(frozen=True)
class TemporalTask:
    task_id: str
    duration_minutes: int
    earliest_start: str
    deadline: str
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduledTask:
    task_id: str
    start: str
    finish: str
    deadline: str
    slack_minutes: int
    dependencies: tuple[str, ...]


@dataclass(frozen=True)
class TemporalPlan:
    boundary: TemporalBoundary
    tasks: tuple[ScheduledTask, ...]
    conflict_task_ids: tuple[str, ...]
    reason: str
    timezone_offsets_preserved: bool
    external_schedule_created: bool


@dataclass(frozen=True)
class RecurrencePreview:
    occurrences: tuple[str, ...]
    bounded: bool
    external_schedule_created: bool


def _parse_aware(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _topological_order(tasks: Sequence[TemporalTask]) -> tuple[TemporalBoundary, tuple[str, ...], str]:
    ids = {task.task_id for task in tasks}
    if len(ids) != len(tasks) or any(not task.task_id for task in tasks):
        return TemporalBoundary.DEPENDENCY_ERROR, (), "task_ids_must_be_unique_and_nonempty"

    for task in tasks:
        if any(dep not in ids for dep in task.dependencies):
            return TemporalBoundary.DEPENDENCY_ERROR, (), f"unknown_dependency:{task.task_id}"
        if task.task_id in task.dependencies:
            return TemporalBoundary.CYCLE_DETECTED, (), f"self_dependency:{task.task_id}"

    remaining = {task.task_id: set(task.dependencies) for task in tasks}
    ordered: list[str] = []
    while remaining:
        ready = sorted(task_id for task_id, deps in remaining.items() if not deps)
        if not ready:
            return TemporalBoundary.CYCLE_DETECTED, (), "dependency_cycle_detected"
        for task_id in ready:
            ordered.append(task_id)
            remaining.pop(task_id)
            for deps in remaining.values():
                deps.discard(task_id)

    return TemporalBoundary.READY, tuple(ordered), "topology_ready"


def plan_temporal_tasks(
    tasks: Sequence[TemporalTask],
    *,
    max_tasks: int = 32,
) -> TemporalPlan:
    bounded = max(1, min(int(max_tasks), 64))
    selected = tuple(tasks[:bounded])

    if not selected:
        return TemporalPlan(
            boundary=TemporalBoundary.NO_TASKS,
            tasks=(),
            conflict_task_ids=(),
            reason="no_tasks",
            timezone_offsets_preserved=True,
            external_schedule_created=False,
        )

    topology_boundary, order, topology_reason = _topological_order(selected)
    if topology_boundary != TemporalBoundary.READY:
        return TemporalPlan(
            boundary=topology_boundary,
            tasks=(),
            conflict_task_ids=(),
            reason=topology_reason,
            timezone_offsets_preserved=True,
            external_schedule_created=False,
        )

    by_id = {task.task_id: task for task in selected}
    parsed: dict[str, tuple[datetime, datetime]] = {}
    for task in selected:
        start = _parse_aware(task.earliest_start)
        deadline = _parse_aware(task.deadline)
        if start is None or deadline is None:
            return TemporalPlan(
                boundary=TemporalBoundary.TIMEZONE_REQUIRED,
                tasks=(),
                conflict_task_ids=(task.task_id,),
                reason=f"timezone_aware_iso_required:{task.task_id}",
                timezone_offsets_preserved=False,
                external_schedule_created=False,
            )
        if deadline < start or int(task.duration_minutes) <= 0:
            return TemporalPlan(
                boundary=TemporalBoundary.INVALID_WINDOW,
                tasks=(),
                conflict_task_ids=(task.task_id,),
                reason=f"invalid_window:{task.task_id}",
                timezone_offsets_preserved=True,
                external_schedule_created=False,
            )
        parsed[task.task_id] = (start, deadline)

    scheduled: dict[str, ScheduledTask] = {}
    conflicts: list[str] = []

    for task_id in order:
        task = by_id[task_id]
        earliest, deadline = parsed[task_id]
        start = earliest

        if task.dependencies:
            dep_finishes = [
                _parse_aware(scheduled[dep].finish)
                for dep in task.dependencies
                if dep in scheduled
            ]
            dep_finishes = [item for item in dep_finishes if item is not None]
            if dep_finishes:
                latest_dependency_finish = max(dep_finishes)
                if latest_dependency_finish > start:
                    start = latest_dependency_finish

        finish = start + timedelta(minutes=int(task.duration_minutes))
        slack = int((deadline - finish).total_seconds() // 60)
        if finish > deadline:
            conflicts.append(task_id)

        scheduled[task_id] = ScheduledTask(
            task_id=task_id,
            start=_iso(start),
            finish=_iso(finish),
            deadline=_iso(deadline),
            slack_minutes=slack,
            dependencies=tuple(task.dependencies),
        )

    boundary = TemporalBoundary.DEADLINE_CONFLICT if conflicts else TemporalBoundary.READY
    return TemporalPlan(
        boundary=boundary,
        tasks=tuple(scheduled[task_id] for task_id in order),
        conflict_task_ids=tuple(conflicts),
        reason="deadline_conflict" if conflicts else "schedule_feasible",
        timezone_offsets_preserved=True,
        external_schedule_created=False,
    )


def preview_recurrence(
    start: str,
    *,
    every_minutes: int,
    occurrences: int,
    max_occurrences: int = 20,
) -> RecurrencePreview:
    dt = _parse_aware(start)
    if dt is None:
        raise ValueError("timezone_aware_iso_required")
    if int(every_minutes) <= 0:
        raise ValueError("every_minutes_must_be_positive")

    cap = max(1, min(int(max_occurrences), 50))
    requested = max(0, int(occurrences))
    count = min(requested, cap)
    values = tuple(
        _iso(dt + timedelta(minutes=int(every_minutes) * index))
        for index in range(count)
    )
    return RecurrencePreview(
        occurrences=values,
        bounded=requested <= cap,
        external_schedule_created=False,
    )


def public_temporal_plan(plan: TemporalPlan) -> dict[str, object]:
    return {
        "boundary": plan.boundary.value,
        "reason": plan.reason,
        "timezone_offsets_preserved": plan.timezone_offsets_preserved,
        "external_schedule_created": plan.external_schedule_created,
        "conflict_task_ids": list(plan.conflict_task_ids),
        "tasks": [
            {
                "task_id": item.task_id,
                "start": item.start,
                "finish": item.finish,
                "deadline": item.deadline,
                "slack_minutes": item.slack_minutes,
                "dependencies": list(item.dependencies),
            }
            for item in plan.tasks
        ],
    }
