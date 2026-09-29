from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class ComparisonRelation(str, Enum):
    AGREES = "AGREES"
    CONTRADICTS = "CONTRADICTS"
    PARTIAL = "PARTIAL"
    UNRELATED = "UNRELATED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EvidenceComparison:
    left_evidence_id: str
    right_evidence_id: str
    relation: ComparisonRelation
    reason: str


def compare_evidence(
    left: dict[str, Any],
    right: dict[str, Any],
    semantic_comparator: Callable[[dict[str, Any], dict[str, Any]], str | None] | None = None,
) -> EvidenceComparison:
    left_id = str(left.get("evidence_id", ""))
    right_id = str(right.get("evidence_id", ""))

    if not left_id or not right_id:
        return EvidenceComparison(
            left_evidence_id=left_id or "unknown-left",
            right_evidence_id=right_id or "unknown-right",
            relation=ComparisonRelation.UNKNOWN,
            reason="Missing evidence identifiers.",
        )

    if left_id == right_id:
        return EvidenceComparison(
            left_evidence_id=left_id,
            right_evidence_id=right_id,
            relation=ComparisonRelation.PARTIAL,
            reason="Evidence records refer to the same item.",
        )

    left_supports = set(_as_text_list(left.get("supports_claim_ids", [])))
    left_contradicts = set(_as_text_list(left.get("contradicts_claim_ids", [])))
    right_supports = set(_as_text_list(right.get("supports_claim_ids", [])))
    right_contradicts = set(_as_text_list(right.get("contradicts_claim_ids", [])))

    if (left_supports & right_contradicts) or (right_supports & left_contradicts):
        return EvidenceComparison(
            left_evidence_id=left_id,
            right_evidence_id=right_id,
            relation=ComparisonRelation.CONTRADICTS,
            reason="Claim support and contradiction metadata conflict.",
        )

    if left_supports and right_supports and (left_supports & right_supports):
        return EvidenceComparison(
            left_evidence_id=left_id,
            right_evidence_id=right_id,
            relation=ComparisonRelation.AGREES,
            reason="Both records support at least one shared claim.",
        )

    left_url = _normalize_text(left.get("url", ""))
    right_url = _normalize_text(right.get("url", ""))

    if left_url and right_url and left_url == right_url:
        return EvidenceComparison(
            left_evidence_id=left_id,
            right_evidence_id=right_id,
            relation=ComparisonRelation.PARTIAL,
            reason="Records share the same normalized URL.",
        )

    left_domain = _normalize_text(left.get("domain", ""))
    right_domain = _normalize_text(right.get("domain", ""))

    if left_domain and right_domain and left_domain == right_domain:
        return EvidenceComparison(
            left_evidence_id=left_id,
            right_evidence_id=right_id,
            relation=ComparisonRelation.PARTIAL,
            reason="Records come from the same normalized domain.",
        )

    if semantic_comparator is not None:
        try:
            semantic_relation = semantic_comparator(left, right)
            if semantic_relation in {item.value for item in ComparisonRelation}:
                relation = ComparisonRelation(semantic_relation)
                return EvidenceComparison(
                    left_evidence_id=left_id,
                    right_evidence_id=right_id,
                    relation=relation,
                    reason="Relation produced by semantic comparator.",
                )
        except Exception:
            return EvidenceComparison(
                left_evidence_id=left_id,
                right_evidence_id=right_id,
                relation=ComparisonRelation.UNKNOWN,
                reason="Semantic comparator failed.",
            )

    if left_supports or left_contradicts or right_supports or right_contradicts:
        return EvidenceComparison(
            left_evidence_id=left_id,
            right_evidence_id=right_id,
            relation=ComparisonRelation.UNRELATED,
            reason="Metadata does not indicate agreement or contradiction.",
        )

    return EvidenceComparison(
        left_evidence_id=left_id,
        right_evidence_id=right_id,
        relation=ComparisonRelation.UNKNOWN,
        reason="Insufficient metadata for deterministic comparison.",
    )


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _as_text_list(items: Any) -> list[str]:
    return [str(item).strip() for item in list(items or []) if str(item).strip()]
