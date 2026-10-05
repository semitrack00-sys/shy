from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


class Modality(str, Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"
    VISION = "VISION"


class FusionBoundary(str, Enum):
    FUSED = "FUSED"
    DATA_REQUIRED = "DATA_REQUIRED"
    CONFLICT_REQUIRES_CLARIFICATION = "CONFLICT_REQUIRES_CLARIFICATION"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class EvidenceUnit:
    modality: Modality
    source_id: str
    content: str
    confidence: float
    provenance_available: bool
    claims: Mapping[str, str]


@dataclass(frozen=True)
class FusionConflict:
    claim_key: str
    values: tuple[str, ...]
    modalities: tuple[str, ...]


@dataclass(frozen=True)
class FusionResult:
    boundary: FusionBoundary
    evidence: tuple[EvidenceUnit, ...]
    modalities: tuple[str, ...]
    conflicts: tuple[FusionConflict, ...]
    source_count: int
    max_sources_enforced: bool
    rejected_reason: str | None


def _clean(value: str, max_chars: int = 4000) -> str:
    return " ".join(str(value or "").strip().split())[:max_chars]


def _normalize_claim(value: str) -> str:
    return _clean(value, 1000).lower()


def build_evidence_unit(
    *,
    modality: str,
    source_id: str,
    content: str,
    confidence: float = 0.7,
    provenance_available: bool = True,
    claims: Mapping[str, str] | None = None,
) -> EvidenceUnit:
    try:
        parsed_modality = Modality(str(modality).strip().upper())
    except Exception as exc:
        raise ValueError("unsupported_modality") from exc

    clean_source = _clean(source_id, 200)
    if not clean_source:
        raise ValueError("source_id_required")

    if parsed_modality == Modality.VISION and not provenance_available:
        raise ValueError("vision_provenance_required")

    return EvidenceUnit(
        modality=parsed_modality,
        source_id=clean_source,
        content=_clean(content, 12000),
        confidence=max(0.0, min(1.0, float(confidence))),
        provenance_available=bool(provenance_available),
        claims={
            _clean(key, 200): _clean(value, 1000)
            for key, value in (claims or {}).items()
            if _clean(key, 200)
        },
    )


def fuse_evidence(
    items: Sequence[EvidenceUnit],
    *,
    max_sources: int = 12,
) -> FusionResult:
    bound = max(1, min(int(max_sources), 32))
    if not items:
        return FusionResult(
            boundary=FusionBoundary.DATA_REQUIRED,
            evidence=(),
            modalities=(),
            conflicts=(),
            source_count=0,
            max_sources_enforced=True,
            rejected_reason="evidence_required",
        )

    unique: list[EvidenceUnit] = []
    seen_sources: set[str] = set()
    for item in items:
        if item.source_id in seen_sources:
            continue
        seen_sources.add(item.source_id)
        unique.append(item)

    truncated = unique[:bound]
    max_sources_enforced = len(unique) <= bound

    if any(item.modality == Modality.VISION and not item.provenance_available for item in truncated):
        return FusionResult(
            boundary=FusionBoundary.REJECTED,
            evidence=(),
            modalities=(),
            conflicts=(),
            source_count=0,
            max_sources_enforced=max_sources_enforced,
            rejected_reason="vision_provenance_required",
        )

    claim_values: dict[str, dict[str, set[str]]] = {}
    for item in truncated:
        for key, value in item.claims.items():
            norm_key = _clean(key, 200).lower()
            norm_value = _normalize_claim(value)
            if not norm_key or not norm_value:
                continue
            entry = claim_values.setdefault(norm_key, {})
            entry.setdefault(norm_value, set()).add(item.modality.value)

    conflicts: list[FusionConflict] = []
    for key, values in claim_values.items():
        if len(values) <= 1:
            continue
        modalities = sorted({modality for mods in values.values() for modality in mods})
        conflicts.append(
            FusionConflict(
                claim_key=key,
                values=tuple(sorted(values.keys())),
                modalities=tuple(modalities),
            )
        )

    modalities = tuple(sorted({item.modality.value for item in truncated}))
    boundary = (
        FusionBoundary.CONFLICT_REQUIRES_CLARIFICATION
        if conflicts
        else FusionBoundary.FUSED
    )

    return FusionResult(
        boundary=boundary,
        evidence=tuple(truncated),
        modalities=modalities,
        conflicts=tuple(sorted(conflicts, key=lambda item: item.claim_key)),
        source_count=len(truncated),
        max_sources_enforced=max_sources_enforced,
        rejected_reason=None,
    )


def public_fusion_metadata(result: FusionResult) -> dict[str, object]:
    return {
        "boundary": result.boundary.value,
        "modalities": list(result.modalities),
        "source_count": result.source_count,
        "max_sources_enforced": result.max_sources_enforced,
        "rejected_reason": result.rejected_reason,
        "conflicts": [
            {
                "claim_key": conflict.claim_key,
                "values": list(conflict.values),
                "modalities": list(conflict.modalities),
            }
            for conflict in result.conflicts
        ],
        "evidence": [
            {
                "modality": item.modality.value,
                "source_id": item.source_id,
                "confidence": round(item.confidence, 6),
                "provenance_available": item.provenance_available,
            }
            for item in result.evidence
        ],
    }
