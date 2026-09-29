import importlib.util
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


services_path = Path(__file__).resolve().parents[1]

citation_module = load_module(
    "shy_citation_validator",
    services_path / "research" / "citation_validator.py",
)

validate_citation_references = citation_module.validate_citation_references


class VerificationOutcome(str, Enum):
    PASS = "PASS"
    CORRECTABLE = "CORRECTABLE"
    FAIL = "FAIL"


class DefectType(str, Enum):
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    CITATION_INVALID = "CITATION_INVALID"
    CITATION_MISMATCH = "CITATION_MISMATCH"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    TOOL_RESULT_MISMATCH = "TOOL_RESULT_MISMATCH"
    INCOMPLETE_RESULT = "INCOMPLETE_RESULT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


class RecommendedAction(str, Enum):
    FINISH = "FINISH"
    REVISE = "REVISE"
    FAIL = "FAIL"


class ClaimType(str, Enum):
    FACTUAL = "FACTUAL"
    INFERENCE = "INFERENCE"
    TOOL_STATE = "TOOL_STATE"


class ClaimVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class EvidenceSourceType(str, Enum):
    WEB_SOURCE = "WEB_SOURCE"
    TOOL_OUTPUT = "TOOL_OUTPUT"
    PLAN_ARTIFACT = "PLAN_ARTIFACT"


class EvidenceReliabilityStatus(str, Enum):
    RELIABLE = "RELIABLE"
    UNRELIABLE = "UNRELIABLE"
    UNKNOWN = "UNKNOWN"


class EvidenceStatus(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    CONTRADICTORY = "CONTRADICTORY"
    MISSING = "MISSING"


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    text: str
    claim_type: ClaimType
    requires_evidence: bool
    evidence_refs: tuple[str, ...] = ()
    citation_refs: tuple[int, ...] = ()
    verification_status: ClaimVerificationStatus = ClaimVerificationStatus.UNKNOWN


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_type: EvidenceSourceType
    source_ref: str
    supports_claim_ids: tuple[str, ...] = ()
    contradicts_claim_ids: tuple[str, ...] = ()
    reliability_status: EvidenceReliabilityStatus = EvidenceReliabilityStatus.UNKNOWN


@dataclass(frozen=True)
class CitationIssueRecord:
    reference: str
    defect: DefectType
    message: str


@dataclass(frozen=True)
class VerificationReport:
    outcome: VerificationOutcome
    issues: tuple[DefectType, ...]
    confidence: float
    verified_claims: tuple[ClaimRecord, ...]
    unsupported_claims: tuple[ClaimRecord, ...]
    citation_issues: tuple[CitationIssueRecord, ...]
    evidence_status: EvidenceStatus
    recommended_action: RecommendedAction
    summary: str

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "issues": [issue.value for issue in self.issues],
            "confidence": self.confidence,
            "verified_claims": [asdict(item) for item in self.verified_claims],
            "unsupported_claims": [asdict(item) for item in self.unsupported_claims],
            "citation_issues": [
                {
                    "reference": issue.reference,
                    "defect": issue.defect.value,
                    "message": issue.message,
                }
                for issue in self.citation_issues
            ],
            "evidence_status": self.evidence_status.value,
            "recommended_action": self.recommended_action.value,
            "summary": self.summary,
        }


def verify_task_result(
    task_state,
    semantic_verifier: Callable[[list[ClaimRecord], list[EvidenceRecord], Any], dict | None]
    | None = None,
) -> VerificationReport:
    try:
        plan_steps = list(getattr(task_state, "plan_steps", []))
    except Exception:
        return _unavailable_report("Task state is unavailable.")

    if not plan_steps:
        return _report(
            outcome=VerificationOutcome.FAIL,
            issues=[DefectType.INCOMPLETE_RESULT],
            confidence=0.0,
            verified_claims=[],
            unsupported_claims=[],
            citation_issues=[],
            evidence_status=EvidenceStatus.MISSING,
            recommended_action=RecommendedAction.FAIL,
            summary="No plan steps available for verification.",
        )

    issues: list[DefectType] = []
    citation_issues: list[CitationIssueRecord] = []

    claims = _extract_claims(plan_steps)
    evidence = _extract_evidence(task_state, plan_steps)

    _validate_tool_result_alignment(plan_steps, issues)

    claim_lookup = {claim.claim_id: claim for claim in claims}
    evidence_by_claim = _build_evidence_map(evidence)

    verified_claims: list[ClaimRecord] = []
    unsupported_claims: list[ClaimRecord] = []

    for claim in claims:
        supporting = evidence_by_claim.get(claim.claim_id, {}).get("supports", [])
        contradicting = evidence_by_claim.get(claim.claim_id, {}).get("contradicts", [])

        status = ClaimVerificationStatus.VERIFIED

        if contradicting and supporting:
            status = ClaimVerificationStatus.CONTRADICTED
            issues.append(DefectType.CONTRADICTORY_EVIDENCE)

        elif claim.requires_evidence and not supporting:
            status = ClaimVerificationStatus.UNSUPPORTED
            issues.append(DefectType.MISSING_EVIDENCE)

        elif claim.requires_evidence and supporting:
            status = ClaimVerificationStatus.VERIFIED

        updated = ClaimRecord(
            claim_id=claim.claim_id,
            text=claim.text,
            claim_type=claim.claim_type,
            requires_evidence=claim.requires_evidence,
            evidence_refs=tuple(item.evidence_id for item in supporting),
            citation_refs=claim.citation_refs,
            verification_status=status,
        )

        if status == ClaimVerificationStatus.VERIFIED:
            verified_claims.append(updated)
        else:
            unsupported_claims.append(updated)

    research_sources = list(getattr(task_state, "research_sources", []))
    combined_text = "\n".join(
        str(getattr(step, "result_summary", "") or "")
        for step in plan_steps
    )

    citation_report = validate_citation_references(
        text=combined_text,
        sources=research_sources,
        require_url=True,
    )

    for item in citation_report.issues:
        defect = DefectType.CITATION_INVALID

        if item.defect == "CITATION_MISMATCH":
            defect = DefectType.CITATION_MISMATCH

        citation_issues.append(
            CitationIssueRecord(
                reference=item.reference,
                defect=defect,
                message=item.message,
            )
        )
        issues.append(defect)

    if _requires_research_evidence(plan_steps) and not research_sources:
        issues.append(DefectType.INSUFFICIENT_EVIDENCE)

    if semantic_verifier is not None:
        semantic = semantic_verifier(claims, evidence, task_state)

        if semantic:
            for issue_name in semantic.get("issues", []):
                try:
                    issues.append(DefectType(issue_name))
                except Exception:
                    issues.append(DefectType.VERIFICATION_UNAVAILABLE)

    unique_issues = tuple(_dedupe_issues(issues))
    evidence_status = _derive_evidence_status(unique_issues, evidence)
    confidence = _derive_confidence(unique_issues, evidence_status, citation_issues)
    outcome, action = _derive_outcome_and_action(unique_issues, evidence_status)

    return _report(
        outcome=outcome,
        issues=list(unique_issues),
        confidence=confidence,
        verified_claims=verified_claims,
        unsupported_claims=unsupported_claims,
        citation_issues=citation_issues,
        evidence_status=evidence_status,
        recommended_action=action,
        summary=_summary_text(outcome, unique_issues),
    )


def _extract_claims(plan_steps: list[Any]) -> list[ClaimRecord]:
    claims: list[ClaimRecord] = []

    for index, step in enumerate(plan_steps, start=1):
        summary = str(getattr(step, "result_summary", "") or "").strip()

        if not summary:
            continue

        claim_type = ClaimType.INFERENCE

        if str(getattr(step, "action_type", "")) == "ActionType.TOOL":
            claim_type = ClaimType.TOOL_STATE
        elif re.search(r"\b(latest|current|research|source|according to)\b", summary, re.I):
            claim_type = ClaimType.FACTUAL

        requires_evidence = claim_type in (ClaimType.FACTUAL, ClaimType.TOOL_STATE)
        citation_refs = tuple(
            sorted(
                {
                    int(value)
                    for value in re.findall(r"\[(\d+)\]", summary)
                }
            )
        )

        claims.append(
            ClaimRecord(
                claim_id=f"claim-{index}",
                text=summary,
                claim_type=claim_type,
                requires_evidence=requires_evidence,
                citation_refs=citation_refs,
            )
        )

    return claims


def _extract_evidence(task_state, plan_steps: list[Any]) -> list[EvidenceRecord]:
    evidence: list[EvidenceRecord] = []

    for step in plan_steps:
        status = str(getattr(step, "status", ""))
        step_id = int(getattr(step, "step_id", 0) or 0)

        if status != "PlanStepStatus.EXECUTED":
            continue

        if str(getattr(step, "action_type", "")) == "ActionType.TOOL":
            evidence.append(
                EvidenceRecord(
                    evidence_id=f"tool-{step_id}",
                    source_type=EvidenceSourceType.TOOL_OUTPUT,
                    source_ref=str(getattr(step, "tool_name", "unknown")),
                    supports_claim_ids=(f"claim-{step_id}",),
                    reliability_status=EvidenceReliabilityStatus.RELIABLE,
                )
            )

    for source in list(getattr(task_state, "research_sources", [])):
        ref = str(source.get("url") or source.get("source") or "unknown")
        source_id = str(source.get("number") or len(evidence) + 1)
        supports = tuple(str(item) for item in source.get("supports_claim_ids", []))
        contradicts = tuple(str(item) for item in source.get("contradicts_claim_ids", []))
        reliability = EvidenceReliabilityStatus.UNKNOWN

        if str(source.get("url", "")).startswith(("http://", "https://")):
            reliability = EvidenceReliabilityStatus.RELIABLE

        evidence.append(
            EvidenceRecord(
                evidence_id=f"web-{source_id}",
                source_type=EvidenceSourceType.WEB_SOURCE,
                source_ref=ref,
                supports_claim_ids=supports,
                contradicts_claim_ids=contradicts,
                reliability_status=reliability,
            )
        )

    return evidence


def _build_evidence_map(evidence: list[EvidenceRecord]) -> dict[str, dict[str, list[EvidenceRecord]]]:
    table: dict[str, dict[str, list[EvidenceRecord]]] = {}

    for item in evidence:
        for claim_id in item.supports_claim_ids:
            bucket = table.setdefault(claim_id, {"supports": [], "contradicts": []})
            bucket["supports"].append(item)

        for claim_id in item.contradicts_claim_ids:
            bucket = table.setdefault(claim_id, {"supports": [], "contradicts": []})
            bucket["contradicts"].append(item)

    return table


def _validate_tool_result_alignment(plan_steps: list[Any], issues: list[DefectType]):
    for step in plan_steps:
        if str(getattr(step, "action_type", "")) != "ActionType.TOOL":
            continue

        summary = str(getattr(step, "result_summary", "") or "")
        expected_tool = str(getattr(step, "tool_name", "") or "")

        if not summary:
            issues.append(DefectType.INCOMPLETE_RESULT)
            continue

        parts = {
            item.split("=", 1)[0].strip(): item.split("=", 1)[1].strip()
            for item in summary.split(";")
            if "=" in item
        }

        actual_tool = parts.get("tool", "")
        tool_status = parts.get("tool_status", "")

        if expected_tool and actual_tool and expected_tool != actual_tool:
            issues.append(DefectType.TOOL_RESULT_MISMATCH)

        if tool_status and tool_status != "EXECUTED":
            issues.append(DefectType.TOOL_RESULT_MISMATCH)


def _requires_research_evidence(plan_steps: list[Any]) -> bool:
    for step in plan_steps:
        tool_name = str(getattr(step, "tool_name", "") or "")

        if tool_name == "web.search":
            return True

    return False


def _dedupe_issues(issues: list[DefectType]) -> list[DefectType]:
    ordered: list[DefectType] = []

    for issue in issues:
        if issue not in ordered:
            ordered.append(issue)

    return ordered


def _derive_evidence_status(
    issues: tuple[DefectType, ...],
    evidence: list[EvidenceRecord],
) -> EvidenceStatus:
    if DefectType.CONTRADICTORY_EVIDENCE in issues:
        return EvidenceStatus.CONTRADICTORY

    if DefectType.MISSING_EVIDENCE in issues or DefectType.INSUFFICIENT_EVIDENCE in issues:
        return EvidenceStatus.INSUFFICIENT

    if not evidence:
        return EvidenceStatus.MISSING

    return EvidenceStatus.SUFFICIENT


def _derive_confidence(
    issues: tuple[DefectType, ...],
    evidence_status: EvidenceStatus,
    citation_issues: list[CitationIssueRecord],
) -> float:
    confidence = 1.0

    confidence -= 0.15 * len(issues)
    confidence -= 0.1 * len(citation_issues)

    if evidence_status in (EvidenceStatus.INSUFFICIENT, EvidenceStatus.MISSING):
        confidence -= 0.25

    if evidence_status == EvidenceStatus.CONTRADICTORY:
        confidence -= 0.35

    return max(0.0, min(1.0, round(confidence, 3)))


def _derive_outcome_and_action(
    issues: tuple[DefectType, ...],
    evidence_status: EvidenceStatus,
) -> tuple[VerificationOutcome, RecommendedAction]:
    if not issues:
        return VerificationOutcome.PASS, RecommendedAction.FINISH

    fatal = {
        DefectType.CONTRADICTORY_EVIDENCE,
        DefectType.TOOL_RESULT_MISMATCH,
        DefectType.VERIFICATION_UNAVAILABLE,
    }

    if any(issue in fatal for issue in issues):
        return VerificationOutcome.FAIL, RecommendedAction.FAIL

    if issues:
        return VerificationOutcome.CORRECTABLE, RecommendedAction.REVISE

    return VerificationOutcome.FAIL, RecommendedAction.FAIL


def _summary_text(
    outcome: VerificationOutcome,
    issues: tuple[DefectType, ...],
) -> str:
    if not issues:
        return "Verification passed with no defects."

    labels = ", ".join(issue.value for issue in issues)
    return f"Verification {outcome.value.lower()} with defects: {labels}."


def _report(
    outcome: VerificationOutcome,
    issues: list[DefectType],
    confidence: float,
    verified_claims: list[ClaimRecord],
    unsupported_claims: list[ClaimRecord],
    citation_issues: list[CitationIssueRecord],
    evidence_status: EvidenceStatus,
    recommended_action: RecommendedAction,
    summary: str,
) -> VerificationReport:
    return VerificationReport(
        outcome=outcome,
        issues=tuple(issues),
        confidence=confidence,
        verified_claims=tuple(verified_claims),
        unsupported_claims=tuple(unsupported_claims),
        citation_issues=tuple(citation_issues),
        evidence_status=evidence_status,
        recommended_action=recommended_action,
        summary=summary,
    )


def _unavailable_report(message: str) -> VerificationReport:
    return VerificationReport(
        outcome=VerificationOutcome.FAIL,
        issues=(DefectType.VERIFICATION_UNAVAILABLE,),
        confidence=0.0,
        verified_claims=(),
        unsupported_claims=(),
        citation_issues=(),
        evidence_status=EvidenceStatus.MISSING,
        recommended_action=RecommendedAction.FAIL,
        summary=message,
    )
