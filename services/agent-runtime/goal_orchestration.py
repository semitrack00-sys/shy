from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Sequence


class GoalStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class GoalStepStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class GoalPermission(str, Enum):
    READ_ONLY = "READ_ONLY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DENIED = "DENIED"


@dataclass(frozen=True)
class GoalMilestone:
    name: str
    description: str
    state_changing: bool = False
    dependencies: tuple[int, ...] = ()


@dataclass(frozen=True)
class GoalStep:
    step_id: int
    name: str
    description: str
    permission: GoalPermission
    dependencies: tuple[int, ...]
    status: GoalStepStatus


@dataclass(frozen=True)
class GoalPlan:
    objective: str
    steps: tuple[GoalStep, ...]
    status: GoalStatus
    max_steps: int
    truncated: bool
    denied_reason: str | None = None


_DENIED_MARKERS = (
    "disable antivirus",
    "disable firewall",
    "bypass security",
    "steal password",
    "dump credentials",
    "run arbitrary shell",
    "powershell",
    "terminal command",
    "delete system32",
)


def _clean(value: str, max_chars: int = 2000) -> str:
    return " ".join(str(value or "").strip().split())[:max_chars]


def _permission_for_milestone(milestone: GoalMilestone) -> GoalPermission:
    text = f"{milestone.name} {milestone.description}".lower()
    if any(marker in text for marker in _DENIED_MARKERS):
        return GoalPermission.DENIED
    return (
        GoalPermission.APPROVAL_REQUIRED
        if milestone.state_changing
        else GoalPermission.READ_ONLY
    )


def build_goal_plan(
    objective: str,
    milestones: Sequence[GoalMilestone],
    *,
    max_steps: int = 12,
) -> GoalPlan:
    objective = _clean(objective, 4000)
    bound = max(1, min(int(max_steps), 24))
    if not objective:
        return GoalPlan("", (), GoalStatus.BLOCKED, bound, False, "objective_required")

    selected = tuple(milestones[:bound])
    truncated = len(milestones) > bound

    steps: list[GoalStep] = []
    known_ids = set(range(1, len(selected) + 1))
    for index, milestone in enumerate(selected, start=1):
        permission = _permission_for_milestone(milestone)
        if permission == GoalPermission.DENIED:
            return GoalPlan(
                objective=objective,
                steps=(),
                status=GoalStatus.BLOCKED,
                max_steps=bound,
                truncated=truncated,
                denied_reason="denied_goal_step",
            )
        dependencies = tuple(sorted(set(int(item) for item in milestone.dependencies)))
        if any(dep not in known_ids or dep >= index for dep in dependencies):
            return GoalPlan(
                objective=objective,
                steps=(),
                status=GoalStatus.BLOCKED,
                max_steps=bound,
                truncated=truncated,
                denied_reason="invalid_goal_dependency",
            )
        status = GoalStepStatus.READY if not dependencies and index == 1 else GoalStepStatus.PENDING
        steps.append(
            GoalStep(
                step_id=index,
                name=_clean(milestone.name, 200),
                description=_clean(milestone.description, 1000),
                permission=permission,
                dependencies=dependencies,
                status=status,
            )
        )

    if not steps:
        return GoalPlan(objective, (), GoalStatus.BLOCKED, bound, truncated, "milestones_required")

    return GoalPlan(
        objective=objective,
        steps=tuple(steps),
        status=GoalStatus.PLANNED,
        max_steps=bound,
        truncated=truncated,
        denied_reason=None,
    )


def advance_goal(
    plan: GoalPlan,
    *,
    completed_step_ids: Sequence[int] = (),
    approved_step_ids: Sequence[int] = (),
    cancel: bool = False,
) -> GoalPlan:
    if cancel:
        return replace(plan, status=GoalStatus.CANCELLED)

    completed = {int(item) for item in completed_step_ids}
    approved = {int(item) for item in approved_step_ids}
    new_steps: list[GoalStep] = []

    for step in plan.steps:
        if step.step_id in completed:
            new_steps.append(replace(step, status=GoalStepStatus.COMPLETED))
            continue

        dependencies_complete = all(dep in completed for dep in step.dependencies)
        if not dependencies_complete:
            new_steps.append(replace(step, status=GoalStepStatus.PENDING))
            continue

        if step.permission == GoalPermission.APPROVAL_REQUIRED and step.step_id not in approved:
            new_steps.append(replace(step, status=GoalStepStatus.AWAITING_APPROVAL))
        else:
            new_steps.append(replace(step, status=GoalStepStatus.READY))

    if new_steps and all(step.status == GoalStepStatus.COMPLETED for step in new_steps):
        status = GoalStatus.COMPLETED
    elif any(step.status == GoalStepStatus.AWAITING_APPROVAL for step in new_steps):
        status = GoalStatus.AWAITING_APPROVAL
    elif any(step.status == GoalStepStatus.READY for step in new_steps):
        status = GoalStatus.IN_PROGRESS
    else:
        status = GoalStatus.BLOCKED

    return GoalPlan(
        objective=plan.objective,
        steps=tuple(new_steps),
        status=status,
        max_steps=plan.max_steps,
        truncated=plan.truncated,
        denied_reason=plan.denied_reason,
    )


def public_goal_plan(plan: GoalPlan) -> dict[str, object]:
    return {
        "objective": plan.objective,
        "status": plan.status.value,
        "max_steps": plan.max_steps,
        "truncated": plan.truncated,
        "denied_reason": plan.denied_reason,
        "steps": [
            {
                "step_id": step.step_id,
                "name": step.name,
                "description": step.description,
                "permission": step.permission.value,
                "dependencies": list(step.dependencies),
                "status": step.status.value,
            }
            for step in plan.steps
        ],
    }
