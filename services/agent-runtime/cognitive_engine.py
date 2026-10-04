from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CognitiveComplexity(str, Enum):
    SIMPLE = "SIMPLE"
    STANDARD = "STANDARD"
    COMPLEX = "COMPLEX"
    DEEP = "DEEP"
    RESEARCH = "RESEARCH"


class VerificationStatus(str, Enum):
    NOT_RUN = "NOT_RUN"
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    FAILED_VERIFICATION = "FAILED_VERIFICATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class UncertaintyType(str, Enum):
    FACT = "FACT"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"
    UNCERTAIN = "UNCERTAIN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProblemUnderstanding:
    problem_type: str
    user_objective: str
    known_facts: tuple[str, ...]
    constraints: tuple[str, ...]
    missing_information: tuple[str, ...]
    assumptions: tuple[str, ...]
    required_output: str
    risk_level: str
    estimated_reasoning_complexity: CognitiveComplexity


@dataclass(frozen=True)
class DecomposedStep:
    step_id: int
    objective: str
    depends_on: tuple[int, ...] = ()
    requires_memory: bool = False
    requires_tools: bool = False
    requires_research: bool = False
    requires_calculation: bool = False
    requires_verification: bool = False
    specialized_model_role: str = "GENERAL"


@dataclass(frozen=True)
class DecompositionPlan:
    steps: tuple[DecomposedStep, ...]
    dependency_edges: int
    bounded: bool


@dataclass(frozen=True)
class Hypothesis:
    name: str
    evidence_for: tuple[str, ...]
    evidence_against: tuple[str, ...]
    confidence: float
    rejected: bool = False
    unresolved: bool = False


@dataclass(frozen=True)
class CandidateApproach:
    name: str
    correctness: float
    feasibility: float
    evidence: float
    cost: float
    risk: float
    constraints_fit: float
    expected_outcome: float


@dataclass(frozen=True)
class CandidateEvaluation:
    selected: CandidateApproach | None
    ranked: tuple[CandidateApproach, ...]


@dataclass(frozen=True)
class CriticIssue:
    issue_type: str
    detail: str
    severity: str


@dataclass(frozen=True)
class CriticResult:
    issues: tuple[CriticIssue, ...]


@dataclass(frozen=True)
class VerifierResult:
    status: VerificationStatus
    summary: str


@dataclass(frozen=True)
class Contradiction:
    field: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class CognitiveMetadata:
    cognitive_mode: str
    complexity: str
    decomposition_count: int
    hypotheses_considered: int
    verification_status: str
    confidence: float
    uncertainty_flags: tuple[str, ...]
    evidence_sources_count: int
    tools_used: tuple[str, ...]
    model_role: str
    selected_provider: str | None
    executed_provider: str | None


def classify_complexity(message: str, requires_external_evidence: bool = False) -> CognitiveComplexity:
    text = " ".join(str(message or "").lower().split())
    if not text:
        return CognitiveComplexity.SIMPLE

    if requires_external_evidence or any(token in text for token in ("research", "latest", "current", "compare sources")):
        return CognitiveComplexity.RESEARCH

    deep_markers = (
        "architecture",
        "tradeoff",
        "trade-off",
        "competing constraints",
        "recommend the best design",
        "evaluate several",
        "multi-phase",
    )
    if any(marker in text for marker in deep_markers):
        return CognitiveComplexity.DEEP

    complex_markers = (
        "diagnose",
        "root cause",
        "analyze",
        "several metrics",
        "constraints",
        "plan",
        "why",
    )
    if any(marker in text for marker in complex_markers) and len(text.split()) >= 8:
        return CognitiveComplexity.COMPLEX

    standard_markers = (
        "compare",
        "pros and cons",
        "option",
        "recommend",
        "difference",
    )
    if any(marker in text for marker in standard_markers):
        return CognitiveComplexity.STANDARD

    return CognitiveComplexity.SIMPLE


def recommended_model_role(complexity: CognitiveComplexity, planning_heavy: bool = False, coding: bool = False) -> str:
    if coding:
        return "CODING"
    if planning_heavy:
        return "PLANNER"
    if complexity == CognitiveComplexity.SIMPLE:
        return "FAST"
    if complexity == CognitiveComplexity.STANDARD:
        return "GENERAL"
    if complexity in {CognitiveComplexity.COMPLEX, CognitiveComplexity.DEEP}:
        return "REASONING"
    if complexity == CognitiveComplexity.RESEARCH:
        return "RESEARCH"
    return "GENERAL"


def understand_problem(
    message: str,
    *,
    known_facts: list[str] | tuple[str, ...] | None = None,
    constraints: list[str] | tuple[str, ...] | None = None,
    required_output: str | None = None,
) -> ProblemUnderstanding:
    text = " ".join(str(message or "").split())
    lowered = text.lower()

    complexity = classify_complexity(text)

    problem_type = "general_reasoning"
    if any(token in lowered for token in ("%", "revenue", "expenses", "profit", "calculate", "math")):
        problem_type = "mathematics"
    elif any(token in lowered for token in ("bug", "exception", "traceback", "error", "build")):
        problem_type = "software"
    elif any(token in lowered for token in ("delivery", "logistics", "dispatch", "late")):
        problem_type = "logistics"
    elif complexity == CognitiveComplexity.RESEARCH:
        problem_type = "research"

    missing: list[str] = []
    assumptions: list[str] = []
    risk_level = "LOW"

    if any(token in lowered for token in ("recommend", "best", "diagnose", "root cause")):
        risk_level = "MEDIUM"
    if complexity in {CognitiveComplexity.DEEP, CognitiveComplexity.RESEARCH}:
        risk_level = "HIGH"

    if "without" in lowered and "data" in lowered:
        missing.append("supporting_data")
    if "assume" in lowered:
        assumptions.append("user-specified assumptions present")

    if complexity == CognitiveComplexity.RESEARCH:
        missing.append("external_evidence")

    output = required_output or "clear_answer"
    if "compare" in lowered:
        output = "comparison"
    if "diagnose" in lowered:
        output = "diagnosis"

    return ProblemUnderstanding(
        problem_type=problem_type,
        user_objective=text,
        known_facts=tuple(known_facts or ()),
        constraints=tuple(constraints or ()),
        missing_information=tuple(missing),
        assumptions=tuple(assumptions),
        required_output=output,
        risk_level=risk_level,
        estimated_reasoning_complexity=complexity,
    )


def decompose_problem(understanding: ProblemUnderstanding, max_subproblems: int = 6, max_dependencies: int = 12) -> DecompositionPlan:
    complexity = understanding.estimated_reasoning_complexity
    if complexity in {CognitiveComplexity.SIMPLE, CognitiveComplexity.STANDARD}:
        steps = (
            DecomposedStep(step_id=1, objective="Solve request directly.", requires_verification=complexity == CognitiveComplexity.STANDARD),
        )
        return DecompositionPlan(steps=steps, dependency_edges=0, bounded=True)

    drafted: list[DecomposedStep] = [
        DecomposedStep(
            step_id=1,
            objective="Extract known facts and constraints.",
            requires_memory=True,
            specialized_model_role="REASONING",
        ),
        DecomposedStep(
            step_id=2,
            objective="Generate candidate explanations or approaches.",
            depends_on=(1,),
            specialized_model_role="REASONING",
        ),
        DecomposedStep(
            step_id=3,
            objective="Evaluate candidates against evidence and constraints.",
            depends_on=(2,),
            requires_calculation=True,
            requires_verification=True,
            specialized_model_role="REASONING",
        ),
        DecomposedStep(
            step_id=4,
            objective="Synthesize final recommendation with uncertainty.",
            depends_on=(3,),
            requires_verification=True,
            specialized_model_role="VERIFIER" if complexity == CognitiveComplexity.DEEP else "REASONING",
        ),
    ]

    if complexity == CognitiveComplexity.RESEARCH:
        drafted.insert(
            2,
            DecomposedStep(
                step_id=3,
                objective="Gather bounded external evidence.",
                depends_on=(1,),
                requires_research=True,
                specialized_model_role="RESEARCH",
            ),
        )
        drafted = [
            drafted[0],
            drafted[1],
            drafted[2],
            DecomposedStep(
                step_id=4,
                objective="Evaluate candidates against evidence and constraints.",
                depends_on=(2, 3),
                requires_calculation=True,
                requires_verification=True,
                specialized_model_role="REASONING",
            ),
            DecomposedStep(
                step_id=5,
                objective="Synthesize final recommendation with citations and uncertainty.",
                depends_on=(4,),
                requires_verification=True,
                specialized_model_role="VERIFIER",
            ),
        ]

    bounded_steps = tuple(drafted[: max(1, max_subproblems)])
    dependency_edges = sum(len(step.depends_on) for step in bounded_steps)
    bounded = len(bounded_steps) <= max_subproblems and dependency_edges <= max_dependencies
    return DecompositionPlan(steps=bounded_steps, dependency_edges=dependency_edges, bounded=bounded)


def build_hypotheses_from_delivery_evidence(
    *,
    total_deliveries: int,
    late_deliveries: int,
    traffic_delays: int,
    loading_delays: int,
    mechanical_delays: int,
) -> tuple[Hypothesis, ...]:
    total_delay_causes = max(traffic_delays + loading_delays + mechanical_delays, 1)

    def _confidence(value: int) -> float:
        return round(value / total_delay_causes, 3)

    traffic = Hypothesis(
        name="traffic",
        evidence_for=(f"traffic_delays={traffic_delays}",),
        evidence_against=(f"loading_delays={loading_delays}" if loading_delays > traffic_delays else "",),
        confidence=_confidence(traffic_delays),
        rejected=traffic_delays < loading_delays,
        unresolved=traffic_delays == loading_delays,
    )
    loading = Hypothesis(
        name="loading_delays",
        evidence_for=(f"loading_delays={loading_delays}",),
        evidence_against=("none",),
        confidence=_confidence(loading_delays),
        rejected=False,
        unresolved=False,
    )
    mechanical = Hypothesis(
        name="mechanical_failures",
        evidence_for=(f"mechanical_delays={mechanical_delays}",),
        evidence_against=(f"loading_delays={loading_delays}",),
        confidence=_confidence(mechanical_delays),
        rejected=mechanical_delays < loading_delays,
        unresolved=False,
    )

    clean = []
    for item in (traffic, loading, mechanical):
        cleaned_against = tuple(token for token in item.evidence_against if token)
        clean.append(
            Hypothesis(
                name=item.name,
                evidence_for=item.evidence_for,
                evidence_against=cleaned_against,
                confidence=item.confidence,
                rejected=item.rejected,
                unresolved=item.unresolved,
            )
        )

    return tuple(clean)


def evaluate_candidates(candidates: list[CandidateApproach]) -> CandidateEvaluation:
    if not candidates:
        return CandidateEvaluation(selected=None, ranked=())

    def _score(candidate: CandidateApproach) -> float:
        return (
            candidate.correctness * 0.25
            + candidate.feasibility * 0.2
            + candidate.evidence * 0.2
            + (1.0 - candidate.cost) * 0.1
            + (1.0 - candidate.risk) * 0.15
            + candidate.constraints_fit * 0.05
            + candidate.expected_outcome * 0.05
        )

    ranked = sorted(candidates, key=_score, reverse=True)
    return CandidateEvaluation(selected=ranked[0], ranked=tuple(ranked))


def detect_contradictions(facts: dict[str, list[Any] | tuple[Any, ...]]) -> tuple[Contradiction, ...]:
    contradictions: list[Contradiction] = []
    for key, values in facts.items():
        normalized = tuple(str(value) for value in values)
        unique = tuple(sorted(set(normalized)))
        if len(unique) > 1:
            contradictions.append(Contradiction(field=key, values=unique))
    return tuple(contradictions)


def run_critic(candidate_answer: dict[str, Any], expected_constraints: dict[str, Any]) -> CriticResult:
    issues: list[CriticIssue] = []

    expected_net = expected_constraints.get("expected_net_profit")
    expected_invest = expected_constraints.get("expected_investment")

    if expected_net is not None and candidate_answer.get("net_profit") != expected_net:
        issues.append(CriticIssue("arithmetic_mistake", "net profit does not match expected value", "HIGH"))

    if expected_invest is not None and candidate_answer.get("investment") != expected_invest:
        issues.append(CriticIssue("arithmetic_mistake", "investment does not match expected value", "HIGH"))

    if expected_constraints.get("must_state_uncertainty") and not candidate_answer.get("uncertainty"):
        issues.append(CriticIssue("missing_uncertainty", "answer omits uncertainty statement", "MEDIUM"))

    if candidate_answer.get("fabricated_evidence"):
        issues.append(CriticIssue("hallucinated_facts", "answer claims unsupported evidence", "HIGH"))

    return CriticResult(issues=tuple(issues))


def verify_calculation(expected: dict[str, float], observed: dict[str, float]) -> VerifierResult:
    if not expected:
        return VerifierResult(
            status=VerificationStatus.INSUFFICIENT_EVIDENCE,
            summary="No expected values were provided for independent verification.",
        )

    matched = 0
    mismatched = 0
    for key, value in expected.items():
        if key not in observed:
            mismatched += 1
            continue
        if float(observed[key]) == float(value):
            matched += 1
        else:
            mismatched += 1

    if mismatched == 0 and matched == len(expected):
        return VerifierResult(status=VerificationStatus.VERIFIED, summary="All independent calculation checks matched.")

    if matched > 0:
        return VerifierResult(
            status=VerificationStatus.PARTIALLY_VERIFIED,
            summary=f"{matched} values matched and {mismatched} values did not match.",
        )

    return VerifierResult(status=VerificationStatus.FAILED_VERIFICATION, summary="Independent verification failed.")


def classify_uncertainty(flags: dict[str, UncertaintyType | str]) -> tuple[str, ...]:
    output: list[str] = []
    for key, value in flags.items():
        tag = value.value if isinstance(value, UncertaintyType) else str(value)
        output.append(f"{key}:{tag}")
    return tuple(sorted(output))


def filter_relevant_memory(records: list[dict[str, Any]], workspace_id: str, business_id: str) -> tuple[dict[str, Any], ...]:
    relevant: list[dict[str, Any]] = []
    for record in records:
        if str(record.get("workspace_id", "")) != str(workspace_id):
            continue
        if str(record.get("business_id", "")) != str(business_id):
            continue
        if str(record.get("status", "ACTIVE")).upper() != "ACTIVE":
            continue
        relevant.append(record)
    return tuple(relevant)


def build_cognitive_metadata(
    *,
    complexity: CognitiveComplexity,
    decomposition: DecompositionPlan | None,
    hypotheses: tuple[Hypothesis, ...] = (),
    verification_status: VerificationStatus = VerificationStatus.NOT_RUN,
    confidence: float = 0.7,
    uncertainty_flags: tuple[str, ...] = (),
    evidence_sources_count: int = 0,
    tools_used: tuple[str, ...] = (),
    model_role: str = "GENERAL",
    selected_provider: str | None = None,
    executed_provider: str | None = None,
) -> CognitiveMetadata:
    mode = "direct"
    if complexity == CognitiveComplexity.RESEARCH:
        mode = "research"
    elif complexity in {CognitiveComplexity.COMPLEX, CognitiveComplexity.DEEP}:
        mode = "deep_reasoning"
    elif complexity == CognitiveComplexity.STANDARD:
        mode = "standard_reasoning"

    bounded_confidence = max(0.0, min(1.0, float(confidence)))
    return CognitiveMetadata(
        cognitive_mode=mode,
        complexity=complexity.value,
        decomposition_count=len(decomposition.steps) if decomposition else 0,
        hypotheses_considered=len(hypotheses),
        verification_status=verification_status.value,
        confidence=bounded_confidence,
        uncertainty_flags=uncertainty_flags,
        evidence_sources_count=max(0, int(evidence_sources_count)),
        tools_used=tools_used,
        model_role=model_role,
        selected_provider=selected_provider,
        executed_provider=executed_provider,
    )
