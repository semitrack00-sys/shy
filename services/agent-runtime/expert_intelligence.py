from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable


class ExpertDomain(str, Enum):
    GENERAL = "GENERAL"
    LOGISTICS = "LOGISTICS"
    SOFTWARE_ENGINEERING = "SOFTWARE_ENGINEERING"
    FINANCIAL_ANALYSIS = "FINANCIAL_ANALYSIS"
    BUSINESS_STRATEGY = "BUSINESS_STRATEGY"
    DATA_ANALYSIS = "DATA_ANALYSIS"
    RESEARCH = "RESEARCH"


class ExpertRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    REGULATED = "REGULATED"


class EvidenceRequirement(str, Enum):
    NONE = "NONE"
    USER_SUPPLIED = "USER_SUPPLIED"
    INTERNAL_KNOWLEDGE = "INTERNAL_KNOWLEDGE"
    EXTERNAL_CURRENT = "EXTERNAL_CURRENT"
    AUTHORITATIVE = "AUTHORITATIVE"


class ExpertAnswerBoundary(str, Enum):
    ANSWER = "ANSWER"
    VERIFY = "VERIFY"
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
    DATA_REQUIRED = "DATA_REQUIRED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    AUTHORITATIVE_EVIDENCE_REQUIRED = "AUTHORITATIVE_EVIDENCE_REQUIRED"


@dataclass(frozen=True)
class ExpertProfile:
    domain: ExpertDomain
    label: str
    default_model_role: str
    base_confidence_ceiling: float
    default_evidence_requirement: EvidenceRequirement
    verification_required: bool
    max_assumptions: int


@dataclass(frozen=True)
class ExpertDecision:
    domain: ExpertDomain
    domain_confidence: float
    risk_level: ExpertRiskLevel
    evidence_requirement: EvidenceRequirement
    requires_verification: bool
    requires_research: bool
    requires_authoritative_sources: bool
    answer_boundary: ExpertAnswerBoundary
    confidence_ceiling: float
    matched_signals: tuple[str, ...]
    profile: ExpertProfile


PROFILES: dict[ExpertDomain, ExpertProfile] = {
    ExpertDomain.GENERAL: ExpertProfile(
        domain=ExpertDomain.GENERAL,
        label="General reasoning",
        default_model_role="GENERAL",
        base_confidence_ceiling=0.84,
        default_evidence_requirement=EvidenceRequirement.NONE,
        verification_required=False,
        max_assumptions=3,
    ),
    ExpertDomain.LOGISTICS: ExpertProfile(
        domain=ExpertDomain.LOGISTICS,
        label="Logistics and operations",
        default_model_role="REASONING",
        base_confidence_ceiling=0.9,
        default_evidence_requirement=EvidenceRequirement.USER_SUPPLIED,
        verification_required=True,
        max_assumptions=2,
    ),
    ExpertDomain.SOFTWARE_ENGINEERING: ExpertProfile(
        domain=ExpertDomain.SOFTWARE_ENGINEERING,
        label="Software engineering",
        default_model_role="CODING",
        base_confidence_ceiling=0.9,
        default_evidence_requirement=EvidenceRequirement.INTERNAL_KNOWLEDGE,
        verification_required=True,
        max_assumptions=2,
    ),
    ExpertDomain.FINANCIAL_ANALYSIS: ExpertProfile(
        domain=ExpertDomain.FINANCIAL_ANALYSIS,
        label="Financial analysis",
        default_model_role="REASONING",
        base_confidence_ceiling=0.86,
        default_evidence_requirement=EvidenceRequirement.USER_SUPPLIED,
        verification_required=True,
        max_assumptions=2,
    ),
    ExpertDomain.BUSINESS_STRATEGY: ExpertProfile(
        domain=ExpertDomain.BUSINESS_STRATEGY,
        label="Business strategy",
        default_model_role="REASONING",
        base_confidence_ceiling=0.84,
        default_evidence_requirement=EvidenceRequirement.USER_SUPPLIED,
        verification_required=True,
        max_assumptions=3,
    ),
    ExpertDomain.DATA_ANALYSIS: ExpertProfile(
        domain=ExpertDomain.DATA_ANALYSIS,
        label="Data analysis",
        default_model_role="REASONING",
        base_confidence_ceiling=0.9,
        default_evidence_requirement=EvidenceRequirement.USER_SUPPLIED,
        verification_required=True,
        max_assumptions=2,
    ),
    ExpertDomain.RESEARCH: ExpertProfile(
        domain=ExpertDomain.RESEARCH,
        label="Research synthesis",
        default_model_role="RESEARCH",
        base_confidence_ceiling=0.82,
        default_evidence_requirement=EvidenceRequirement.EXTERNAL_CURRENT,
        verification_required=True,
        max_assumptions=1,
    ),
}


_DOMAIN_MARKERS: dict[ExpertDomain, tuple[tuple[str, float], ...]] = {
    ExpertDomain.LOGISTICS: (
        ("delivery", 2.0),
        ("deliveries", 2.0),
        ("dispatch", 2.2),
        ("fleet", 2.0),
        ("freight", 2.0),
        ("truck", 1.8),
        ("driver", 1.5),
        ("shipment", 1.8),
        ("loading delay", 2.5),
        ("late delivery", 2.5),
        ("route", 1.1),
        ("warehouse", 1.4),
    ),
    ExpertDomain.SOFTWARE_ENGINEERING: (
        ("code", 1.8),
        ("bug", 2.2),
        ("exception", 2.2),
        ("traceback", 2.4),
        ("api", 1.8),
        ("docker", 2.0),
        ("python", 1.8),
        ("typescript", 1.8),
        ("flutter", 1.8),
        ("github", 1.7),
        ("deploy", 1.5),
        ("database schema", 1.8),
        ("software architecture", 2.4),
        ("unit test", 1.8),
    ),
    ExpertDomain.FINANCIAL_ANALYSIS: (
        ("profit", 1.8),
        ("revenue", 1.7),
        ("cash flow", 2.2),
        ("roi", 2.2),
        ("investment", 1.7),
        ("break-even", 2.3),
        ("break even", 2.3),
        ("margin", 1.5),
        ("loan", 1.5),
        ("interest rate", 1.7),
        ("monthly cost", 1.4),
        ("savings", 1.2),
    ),
    ExpertDomain.BUSINESS_STRATEGY: (
        ("business strategy", 2.5),
        ("pricing", 1.8),
        ("customer acquisition", 2.0),
        ("market entry", 2.1),
        ("competitor", 1.8),
        ("business plan", 2.0),
        ("go to market", 2.2),
        ("go-to-market", 2.2),
        ("growth strategy", 2.2),
        ("operations", 1.1),
    ),
    ExpertDomain.DATA_ANALYSIS: (
        ("dataset", 2.2),
        ("statistics", 2.0),
        ("standard deviation", 2.3),
        ("variance", 2.0),
        ("correlation", 2.0),
        ("regression", 2.0),
        ("forecast", 1.6),
        ("metrics", 1.4),
        ("analyze these numbers", 2.0),
        ("trend", 1.2),
    ),
    ExpertDomain.RESEARCH: (
        ("research", 2.5),
        ("compare sources", 2.5),
        ("citations", 2.0),
        ("cite sources", 2.2),
        ("evidence from sources", 2.2),
        ("latest news", 2.4),
    ),
}


_CURRENT_MARKERS = (
    "latest",
    "current price",
    "current market",
    "today's price",
    "todays price",
    "live price",
    "right now",
    "this week",
    "latest news",
    "current law",
    "current regulation",
)


_REGULATED_MARKERS = (
    "diagnose my",
    "medical diagnosis",
    "prescription",
    "dosage",
    "legal advice",
    "is this legal",
    "lawsuit",
    "contract enforceable",
    "file my taxes",
    "tax return",
    "irs",
)


_HIGH_STAKES_FINANCE_MARKERS = (
    "should i buy this stock",
    "should i sell this stock",
    "invest my retirement",
    "retirement portfolio",
    "options trade",
    "buy crypto",
    "sell crypto",
)


_VERIFICATION_MARKERS = (
    "calculate",
    "verify",
    "compare",
    "recommend",
    "diagnose",
    "root cause",
    "should i",
    "is it worth",
    "best option",
)


def _normalize(message: str) -> str:
    return " ".join(str(message or "").lower().split())


def _contains_phrase(text: str, phrase: str) -> bool:
    if " " in phrase or "-" in phrase:
        return phrase in text
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _domain_scores(text: str) -> tuple[dict[ExpertDomain, float], dict[ExpertDomain, list[str]]]:
    scores = {domain: 0.0 for domain in ExpertDomain if domain != ExpertDomain.GENERAL}
    signals: dict[ExpertDomain, list[str]] = {domain: [] for domain in scores}

    for domain, markers in _DOMAIN_MARKERS.items():
        for marker, weight in markers:
            if _contains_phrase(text, marker):
                scores[domain] += weight
                signals[domain].append(marker)

    return scores, signals


def _pick_domain(text: str) -> tuple[ExpertDomain, float, tuple[str, ...]]:
    scores, signals = _domain_scores(text)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0].value))
    if not ranked or ranked[0][1] <= 0:
        return ExpertDomain.GENERAL, 0.5, ()

    best_domain, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    # Prefer the operational domain over finance when a request is clearly
    # about logistics economics; financial math remains an analysis method.
    if (
        scores.get(ExpertDomain.LOGISTICS, 0.0) >= 3.0
        and scores.get(ExpertDomain.FINANCIAL_ANALYSIS, 0.0) > 0
    ):
        best_domain = ExpertDomain.LOGISTICS
        best_score = scores[ExpertDomain.LOGISTICS]
        competing = [
            score
            for domain, score in scores.items()
            if domain != ExpertDomain.LOGISTICS
        ]
        second_score = max(competing or [0.0])

    separation = max(0.0, best_score - second_score)
    confidence = min(0.97, 0.58 + min(best_score, 6.0) * 0.055 + min(separation, 3.0) * 0.035)
    return best_domain, round(confidence, 3), tuple(sorted(set(signals.get(best_domain, []))))


def _risk_level(text: str) -> ExpertRiskLevel:
    if any(marker in text for marker in _REGULATED_MARKERS):
        return ExpertRiskLevel.REGULATED
    if any(marker in text for marker in _HIGH_STAKES_FINANCE_MARKERS):
        return ExpertRiskLevel.HIGH
    if any(
        marker in text
        for marker in (
            "recommend",
            "diagnose",
            "root cause",
            "should i",
            "whether i should",
            "should buy",
            "should purchase",
            "is it worth",
        )
    ):
        return ExpertRiskLevel.MEDIUM
    return ExpertRiskLevel.LOW


def _boundary_from_knowledge(knowledge_boundary: str | None) -> ExpertAnswerBoundary | None:
    normalized = str(knowledge_boundary or "").strip().upper()
    if normalized in {"CONFLICTING_KNOWLEDGE", "CONFLICT"}:
        return ExpertAnswerBoundary.CLARIFICATION_REQUIRED
    if normalized in {"DATA_REQUIRED", "INSUFFICIENT_EVIDENCE", "MISSING_KNOWLEDGE"}:
        return ExpertAnswerBoundary.DATA_REQUIRED
    return None


def select_expert(
    message: str,
    *,
    knowledge_boundary: str | None = None,
    evidence_sources_count: int = 0,
) -> ExpertDecision:
    text = _normalize(message)
    domain, domain_confidence, matched_signals = _pick_domain(text)
    profile = PROFILES[domain]
    risk = _risk_level(text)

    current_required = any(marker in text for marker in _CURRENT_MARKERS)
    verification_required = profile.verification_required or any(marker in text for marker in _VERIFICATION_MARKERS)
    requires_research = domain == ExpertDomain.RESEARCH or current_required
    requires_authoritative = risk == ExpertRiskLevel.REGULATED

    evidence_requirement = profile.default_evidence_requirement
    if current_required:
        evidence_requirement = EvidenceRequirement.EXTERNAL_CURRENT
    if risk == ExpertRiskLevel.REGULATED:
        evidence_requirement = EvidenceRequirement.AUTHORITATIVE
        requires_research = True
        verification_required = True
    elif risk == ExpertRiskLevel.HIGH:
        evidence_requirement = EvidenceRequirement.AUTHORITATIVE
        requires_research = True
        verification_required = True

    boundary = _boundary_from_knowledge(knowledge_boundary)
    if boundary is None:
        if requires_authoritative and evidence_sources_count <= 0:
            boundary = ExpertAnswerBoundary.AUTHORITATIVE_EVIDENCE_REQUIRED
        elif requires_research and evidence_sources_count <= 0:
            boundary = ExpertAnswerBoundary.RESEARCH_REQUIRED
        elif verification_required:
            boundary = ExpertAnswerBoundary.VERIFY
        else:
            boundary = ExpertAnswerBoundary.ANSWER

    confidence_ceiling = profile.base_confidence_ceiling
    normalized_boundary = str(knowledge_boundary or "").strip().upper()
    if normalized_boundary in {"CONFLICTING_KNOWLEDGE", "CONFLICT"}:
        confidence_ceiling = min(confidence_ceiling, 0.45)
    elif normalized_boundary in {"DATA_REQUIRED", "INSUFFICIENT_EVIDENCE", "MISSING_KNOWLEDGE"}:
        confidence_ceiling = min(confidence_ceiling, 0.55)
    elif requires_authoritative and evidence_sources_count <= 0:
        confidence_ceiling = min(confidence_ceiling, 0.5)
    elif requires_research and evidence_sources_count <= 0:
        confidence_ceiling = min(confidence_ceiling, 0.62)

    if risk == ExpertRiskLevel.HIGH:
        confidence_ceiling = min(confidence_ceiling, 0.68)
    if risk == ExpertRiskLevel.REGULATED:
        confidence_ceiling = min(confidence_ceiling, 0.58)

    return ExpertDecision(
        domain=domain,
        domain_confidence=domain_confidence,
        risk_level=risk,
        evidence_requirement=evidence_requirement,
        requires_verification=verification_required,
        requires_research=requires_research,
        requires_authoritative_sources=requires_authoritative,
        answer_boundary=boundary,
        confidence_ceiling=round(max(0.0, min(1.0, confidence_ceiling)), 3),
        matched_signals=matched_signals,
        profile=profile,
    )


def public_expert_metadata(decision: ExpertDecision) -> dict[str, object]:
    # Do not expose classifier markers or internal matching rationale.
    return {
        "domain": decision.domain.value,
        "domain_confidence": decision.domain_confidence,
        "risk_level": decision.risk_level.value,
        "evidence_requirement": decision.evidence_requirement.value,
        "requires_verification": decision.requires_verification,
        "requires_research": decision.requires_research,
        "requires_authoritative_sources": decision.requires_authoritative_sources,
        "answer_boundary": decision.answer_boundary.value,
        "confidence_ceiling": decision.confidence_ceiling,
        "expert_role": decision.profile.default_model_role,
        "max_assumptions": decision.profile.max_assumptions,
    }


def supported_expert_domains() -> tuple[str, ...]:
    return tuple(domain.value for domain in ExpertDomain)
