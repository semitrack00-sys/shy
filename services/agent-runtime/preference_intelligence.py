from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class PreferenceSource(str, Enum):
    EXPLICIT = "EXPLICIT"
    VERIFIED_OUTCOME = "VERIFIED_OUTCOME"
    INFERRED = "INFERRED"


class PreferenceScope(str, Enum):
    USER = "USER"
    WORKSPACE = "WORKSPACE"


@dataclass(frozen=True)
class PreferenceUpdate:
    key: str
    value: str
    source: PreferenceSource
    scope: PreferenceScope
    confidence: float = 1.0


@dataclass(frozen=True)
class PreferenceRecord:
    key: str
    value: str
    source: PreferenceSource
    scope: PreferenceScope
    confidence: float


@dataclass(frozen=True)
class PreferenceEvaluation:
    accepted: bool
    record: PreferenceRecord | None
    reason: str


_PROTECTED_PROFILE_MARKERS = (
    "health",
    "medical",
    "diagnosis",
    "race",
    "ethnicity",
    "religion",
    "political",
    "party",
    "union",
    "sexual",
    "sex life",
    "criminal",
    "password",
    "secret",
    "credential",
    "security question",
)


def _clean(value: str, max_chars: int = 1000) -> str:
    return " ".join(str(value or "").strip().split())[:max_chars]


def is_protected_preference_key(key: str) -> bool:
    normalized = _clean(key, 200).lower().replace("_", " ")
    return any(marker in normalized for marker in _PROTECTED_PROFILE_MARKERS)


def evaluate_preference_update(update: PreferenceUpdate) -> PreferenceEvaluation:
    key = _clean(update.key, 200)
    value = _clean(update.value, 1000)

    if not key:
        return PreferenceEvaluation(False, None, "preference_key_required")
    if not value:
        return PreferenceEvaluation(False, None, "preference_value_required")
    if is_protected_preference_key(key):
        return PreferenceEvaluation(False, None, "protected_preference_category")
    if update.source == PreferenceSource.INFERRED:
        return PreferenceEvaluation(False, None, "implicit_preference_learning_disabled")
    if update.source not in {PreferenceSource.EXPLICIT, PreferenceSource.VERIFIED_OUTCOME}:
        return PreferenceEvaluation(False, None, "unsupported_preference_source")

    confidence = max(0.0, min(1.0, float(update.confidence)))
    if update.source == PreferenceSource.VERIFIED_OUTCOME and confidence < 0.75:
        return PreferenceEvaluation(False, None, "verified_preference_confidence_too_low")

    return PreferenceEvaluation(
        True,
        PreferenceRecord(
            key=key,
            value=value,
            source=update.source,
            scope=update.scope,
            confidence=round(confidence, 6),
        ),
        "accepted",
    )


def build_preference_profile(
    records: Sequence[PreferenceRecord],
    *,
    scope: PreferenceScope,
    max_preferences: int = 50,
) -> tuple[PreferenceRecord, ...]:
    bound = max(1, min(int(max_preferences), 100))
    selected: dict[str, PreferenceRecord] = {}

    for record in records:
        if record.scope != scope:
            continue
        if is_protected_preference_key(record.key):
            continue
        selected[record.key.lower()] = record

    ordered = sorted(
        selected.values(),
        key=lambda item: (-item.confidence, item.key.lower()),
    )
    return tuple(ordered[:bound])


def public_preference_evaluation(result: PreferenceEvaluation) -> dict[str, object]:
    return {
        "accepted": result.accepted,
        "reason": result.reason,
        "record": (
            {
                "key": result.record.key,
                "value": result.record.value,
                "source": result.record.source.value,
                "scope": result.record.scope.value,
                "confidence": result.record.confidence,
            }
            if result.record
            else None
        ),
    }


def public_preference_profile(records: Sequence[PreferenceRecord]) -> dict[str, object]:
    return {
        "count": len(records),
        "preferences": [
            {
                "key": item.key,
                "value": item.value,
                "source": item.source.value,
                "scope": item.scope.value,
                "confidence": item.confidence,
            }
            for item in records
        ],
    }
