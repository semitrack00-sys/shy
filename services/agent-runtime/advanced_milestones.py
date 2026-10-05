from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AdvancedBoundary(str, Enum):
    READY = "READY"
    INVALID_INPUT = "INVALID_INPUT"
    DATA_REQUIRED = "DATA_REQUIRED"
    PROTECTED_TARGET = "PROTECTED_TARGET"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class AdvancedResult:
    capability: str
    boundary: AdvancedBoundary
    reason: str
    payload: dict[str, object]
    side_effect_performed: bool


_PROTECTED_RECOVERY_MARKERS = (
    "security policy",
    "credentials",
    "password",
    "private key",
    "authentication",
    "authorization",
    "permission store",
)


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _recovery_rollback(payload: Mapping[str, object]) -> AdvancedResult:
    target = str(payload.get("target_checkpoint") or "").strip()
    raw_checkpoints = payload.get("checkpoints") or []

    if not isinstance(raw_checkpoints, list):
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.INVALID_INPUT,
            "checkpoints_must_be_a_list",
            {},
            False,
        )

    checkpoints: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in raw_checkpoints[:64]:
        if not isinstance(raw, dict):
            continue
        checkpoint_id = str(raw.get("checkpoint_id") or "").strip()
        if not checkpoint_id or checkpoint_id in seen:
            return AdvancedResult(
                "recovery_rollback",
                AdvancedBoundary.INVALID_INPUT,
                "checkpoint_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(checkpoint_id)
        checkpoints.append(
            {
                "checkpoint_id": checkpoint_id,
                "verified": bool(raw.get("verified", False)),
                "description": str(raw.get("description") or "").strip()[:500],
            }
        )

    if not target:
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.DATA_REQUIRED,
            "target_checkpoint_required",
            {"checkpoint_count": len(checkpoints)},
            False,
        )

    protected_text = _norm(payload.get("target_resource")) + " " + _norm(payload.get("objective"))
    if any(marker in protected_text for marker in _PROTECTED_RECOVERY_MARKERS):
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.PROTECTED_TARGET,
            "protected_security_or_credential_target",
            {"target_checkpoint": target},
            False,
        )

    selected = next((item for item in checkpoints if item["checkpoint_id"] == target), None)
    if selected is None:
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.DATA_REQUIRED,
            "target_checkpoint_not_found",
            {"target_checkpoint": target, "checkpoint_count": len(checkpoints)},
            False,
        )

    if not bool(selected["verified"]):
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.CONFLICT,
            "verified_checkpoint_required",
            {"target_checkpoint": target, "verified": False},
            False,
        )

    return AdvancedResult(
        "recovery_rollback",
        AdvancedBoundary.READY,
        "rollback_plan_ready",
        {
            "target_checkpoint": target,
            "verified": True,
            "plan_steps": [
                "capture_current_state",
                "verify_target_checkpoint",
                "request_execution_approval",
                "execute_via_authorized_runtime_only",
                "verify_post_recovery_state",
            ],
            "execution_allowed_here": False,
        },
        False,
    )


_EVALUATORS = {
    "recovery_rollback": _recovery_rollback,
}


def available_advanced_capabilities() -> tuple[str, ...]:
    return tuple(sorted(_EVALUATORS))


def evaluate_advanced_capability(
    capability: str,
    payload: Mapping[str, object],
) -> AdvancedResult:
    key = _norm(capability).replace(" ", "_")
    evaluator = _EVALUATORS.get(key)
    if evaluator is None:
        return AdvancedResult(
            key,
            AdvancedBoundary.INVALID_INPUT,
            "unsupported_advanced_capability",
            {"available_capabilities": list(available_advanced_capabilities())},
            False,
        )
    return evaluator(payload)


def public_advanced_result(result: AdvancedResult) -> dict[str, object]:
    return {
        "capability": result.capability,
        "boundary": result.boundary.value,
        "reason": result.reason,
        "payload": dict(result.payload),
        "side_effect_performed": result.side_effect_performed,
    }
