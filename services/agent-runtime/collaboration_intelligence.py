from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class DelegationPermission(str, Enum):
    READ_ONLY = "READ_ONLY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DENIED = "DENIED"


class DelegationBoundary(str, Enum):
    READY = "READY"
    INVALID_TASK = "INVALID_TASK"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    PROTECTED_SCOPE = "PROTECTED_SCOPE"


@dataclass(frozen=True)
class DelegationTask:
    task_id: str
    role: str
    objective: str
    scope: str
    permission: DelegationPermission
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class DelegationStep:
    task_id: str
    role: str
    objective: str
    scope: str
    permission: DelegationPermission
    dependencies: tuple[str, ...]
    approval_required: bool


@dataclass(frozen=True)
class DelegationPlan:
    boundary: DelegationBoundary
    steps: tuple[DelegationStep, ...]
    denied_task_ids: tuple[str, ...]
    reason: str
    dispatch_performed: bool
    permissions_expanded: bool


_PROTECTED_MARKERS = (
    "security policy",
    "permission override",
    "approval bypass",
    "credentials",
    "password",
    "secret",
    "private key",
    "authentication token",
)


def _norm(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _topology(tasks: Sequence[DelegationTask]) -> tuple[DelegationBoundary, tuple[str, ...], str]:
    ids = {item.task_id for item in tasks}
    if len(ids) != len(tasks) or any(not item.task_id for item in tasks):
        return DelegationBoundary.INVALID_TASK, (), "task_ids_must_be_unique_and_nonempty"
    for item in tasks:
        if any(dep not in ids for dep in item.dependencies):
            return DelegationBoundary.DEPENDENCY_ERROR, (), f"unknown_dependency:{item.task_id}"
        if item.task_id in item.dependencies:
            return DelegationBoundary.CYCLE_DETECTED, (), f"self_dependency:{item.task_id}"

    remaining = {item.task_id: set(item.dependencies) for item in tasks}
    order: list[str] = []
    while remaining:
        ready = sorted(task_id for task_id, deps in remaining.items() if not deps)
        if not ready:
            return DelegationBoundary.CYCLE_DETECTED, (), "dependency_cycle_detected"
        for task_id in ready:
            order.append(task_id)
            remaining.pop(task_id)
            for deps in remaining.values():
                deps.discard(task_id)
    return DelegationBoundary.READY, tuple(order), "delegation_plan_ready"


def plan_delegation(
    tasks: Sequence[DelegationTask],
    *,
    max_tasks: int = 32,
) -> DelegationPlan:
    cap = max(1, min(int(max_tasks), 64))
    selected = tuple(tasks[:cap])

    boundary, order, reason = _topology(selected)
    if boundary != DelegationBoundary.READY:
        return DelegationPlan(boundary, (), (), reason, False, False)

    by_id = {item.task_id: item for item in selected}
    denied: list[str] = []
    steps: list[DelegationStep] = []

    for task_id in order:
        item = by_id[task_id]
        text = _norm(item.objective + " " + item.scope)
        if any(marker in text for marker in _PROTECTED_MARKERS):
            denied.append(task_id)
            continue
        if not str(item.role or "").strip() or not str(item.scope or "").strip():
            return DelegationPlan(
                DelegationBoundary.INVALID_TASK,
                (),
                (),
                f"role_and_scope_required:{task_id}",
                False,
                False,
            )
        if item.permission == DelegationPermission.DENIED:
            denied.append(task_id)
            continue

        steps.append(
            DelegationStep(
                task_id=task_id,
                role=item.role.strip(),
                objective=item.objective.strip(),
                scope=item.scope.strip(),
                permission=item.permission,
                dependencies=tuple(item.dependencies),
                approval_required=item.permission == DelegationPermission.APPROVAL_REQUIRED,
            )
        )

    if denied:
        return DelegationPlan(
            DelegationBoundary.PROTECTED_SCOPE,
            tuple(steps),
            tuple(denied),
            "one_or_more_tasks_not_delegable",
            False,
            False,
        )

    return DelegationPlan(
        DelegationBoundary.READY,
        tuple(steps),
        (),
        "delegation_plan_ready",
        False,
        False,
    )


def public_delegation_plan(plan: DelegationPlan) -> dict[str, object]:
    return {
        "boundary": plan.boundary.value,
        "reason": plan.reason,
        "denied_task_ids": list(plan.denied_task_ids),
        "dispatch_performed": plan.dispatch_performed,
        "permissions_expanded": plan.permissions_expanded,
        "steps": [
            {
                "task_id": item.task_id,
                "role": item.role,
                "objective": item.objective,
                "scope": item.scope,
                "permission": item.permission.value,
                "dependencies": list(item.dependencies),
                "approval_required": item.approval_required,
            }
            for item in plan.steps
        ],
    }
