from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class PreferenceScope(str, Enum):
    USER = "USER"
    WORKSPACE = "WORKSPACE"


class PreferenceDecision(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class PreferenceUpdate:
    scope: PreferenceScope
    key: str
    value: str
    explicit: bool
    confidence: float = 1.0


@dataclass(frozen=True)
class PreferenceResult:
    decision: PreferenceDecision
    scope: PreferenceScope
    key: str
    value: str | None
    confidence: float
    reason: str


_PROTECTED_MARKERS = (
    "security",
    "permission",
    "approval",
    "authorization",
    "authentication",
    "password",
    "secret",
    "credential",
    "privacy policy",
    "safety",
    "guardrail",
    "tool policy",
)

_SENSITIVE_PROFILE_MARKERS = (
    "race",
    "ethnicity",
    "religion",
    "political",
    "sexual",
    "medical",
    "health condition",
    "criminal",
    "union",
)


def _norm(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def evaluate_preference(update: PreferenceUpdate) -> PreferenceResult:
    key = _norm(update.key)
    value = " ".join(str(update.value or "").strip().split())[:500]

    if not key:
        return PreferenceResult(PreferenceDecision.REJECTED, update.scope, key, None, 0.0, "preference_key_required")

    if any(marker in key for marker in _PROTECTED_MARKERS):
        return PreferenceResult(PreferenceDecision.REJECTED, update.scope, key, None, 0.0, "protected_policy_target")

    if any(marker in key for marker in _SENSITIVE_PROFILE_MARKERS):
        return PreferenceResult(PreferenceDecision.REJECTED, update.scope, key, None, 0.0, "sensitive_profile_target")

    if not update.explicit:
        return PreferenceResult(PreferenceDecision.REJECTED, update.scope, key, None, 0.0, "explicit_preference_required")

    if not value:
        return PreferenceResult(PreferenceDecision.REJECTED, update.scope, key, None, 0.0, "preference_value_required")

    confidence = max(0.0, min(1.0, float(update.confidence)))
    return PreferenceResult(
        PreferenceDecision.ACCEPTED,
        update.scope,
        key,
        value,
        confidence,
        "explicit_preference_accepted",
    )


def apply_preference(
    current: Mapping[str, str],
    result: PreferenceResult,
    *,
    max_preferences: int = 64,
) -> dict[str, str]:
    bounded = max(1, min(int(max_preferences), 128))
    state = {str(k): str(v) for k, v in current.items()}

    if result.decision != PreferenceDecision.ACCEPTED or result.value is None:
        return state

    if result.key not in state and len(state) >= bounded:
        return state

    state[result.key] = result.value
    return state


def public_preference_metadata(result: PreferenceResult) -> dict[str, object]:
    return {
        "decision": result.decision.value,
        "scope": result.scope.value,
        "key": result.key,
        "confidence": round(result.confidence, 6),
        "reason": result.reason,
        "value_stored": result.decision == PreferenceDecision.ACCEPTED,
    }
