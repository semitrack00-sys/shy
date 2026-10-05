from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable
from urllib.parse import urlparse
import importlib.util
import time
from pathlib import Path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


research_path = Path(__file__).resolve().parent

query_planner_module = load_module(
    "shy_query_planner",
    research_path / "query_planner.py",
)

compare_module = load_module(
    "shy_evidence_compare",
    research_path / "evidence_compare.py",
)

QueryPlanner = query_planner_module.QueryPlanner
ResearchPlan = query_planner_module.ResearchPlan
ResearchQuery = query_planner_module.ResearchQuery
QueryStatus = query_planner_module.QueryStatus
ComparisonRelation = compare_module.ComparisonRelation
compare_evidence = compare_module.compare_evidence


class ResearchStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class GapType(str, Enum):
    NO_RESULTS = "NO_RESULTS"
    INSUFFICIENT_SOURCE_DIVERSITY = "INSUFFICIENT_SOURCE_DIVERSITY"
    CLAIM_WITHOUT_EVIDENCE = "CLAIM_WITHOUT_EVIDENCE"
    CONFLICT_REQUIRES_FOLLOWUP = "CONFLICT_REQUIRES_FOLLOWUP"
    QUERY_FAILED = "QUERY_FAILED"


@dataclass(frozen=True)
class ResearchClaim:
    claim_id: str
    text: str
    requires_evidence: bool = True


@dataclass(frozen=True)
class NormalizedEvidence:
    evidence_id: str
    query_id: str
    title: str
    url: str
    domain: str
    snippet: str
    source_rank: int
    supports_claim_ids: tuple[str, ...] = ()
    contradicts_claim_ids: tuple[str, ...] = ()
    retrieved_from: str = "web.search"


@dataclass(frozen=True)
class EvidenceGap:
    gap_type: GapType
    query_id: str | None
    detail: str
    follow_up_allowed: bool


@dataclass(frozen=True)
class EvidenceConflict:
    left_evidence_id: str
    right_evidence_id: str
    relation: str
    reason: str


@dataclass(frozen=True)
class ResearchResult:
    objective: str
    queries_executed: tuple[ResearchQuery, ...]
    sources: tuple[dict[str, Any], ...]
    evidence: tuple[NormalizedEvidence, ...]
    gaps: tuple[EvidenceGap, ...]
    conflicts: tuple[EvidenceConflict, ...]
    unique_domains: int
    source_count: int
    duplicate_count: int
    follow_up_queries_used: int
    status: ResearchStatus

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "queries_executed": [
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "purpose": query.purpose,
                    "priority": query.priority,
                    "status": query.status.value,
                    "parent_query_id": query.parent_query_id,
                }
                for query in self.queries_executed
            ],
            "sources": list(self.sources),
            "evidence": [asdict(item) for item in self.evidence],
            "gaps": [
                {
                    "gap_type": gap.gap_type.value,
                    "query_id": gap.query_id,
                    "detail": gap.detail,
                    "follow_up_allowed": gap.follow_up_allowed,
                }
                for gap in self.gaps
            ],
            "conflicts": [asdict(item) for item in self.conflicts],
            "unique_domains": self.unique_domains,
            "source_count": self.source_count,
            "duplicate_count": self.duplicate_count,
            "follow_up_queries_used": self.follow_up_queries_used,
            "status": self.status.value,
        }

    def to_verifier_payload(self) -> dict[str, Any]:
        return {
            "research_status": self.status.value,
            "research_sources": list(self.sources),
            "research_conflicts": [asdict(item) for item in self.conflicts],
            "research_gaps": [
                {
                    "gap_type": gap.gap_type.value,
                    "query_id": gap.query_id,
                    "detail": gap.detail,
                }
                for gap in self.gaps
            ],
            "unique_domains": self.unique_domains,
            "duplicate_count": self.duplicate_count,
        }


class ResearchEngine:
    """Bounded, provider-independent multi-query research orchestrator."""

    def __init__(
        self,
        search_executor: Callable[[str, int], dict[str, Any]],
        query_planner: QueryPlanner | None = None,
        semantic_comparator: Callable[[dict[str, Any], dict[str, Any]], str | None] | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.search_executor = search_executor
        self.query_planner = query_planner or QueryPlanner()
        self.semantic_comparator = semantic_comparator
        self.clock = clock or time.monotonic

    def run(
        self,
        objective: str,
        claims: list[dict[str, Any]] | None = None,
        max_queries: int | None = None,
        follow_up_budget: int | None = None,
        max_results_per_query: int = 5,
        time_budget_seconds: float | None = None,
    ) -> ResearchResult:
        plan = self.query_planner.create_plan(
            objective=objective,
            max_queries=max_queries,
            follow_up_budget=follow_up_budget,
        )

        claim_records = _normalize_claims(claims)
        executed_queries: list[ResearchQuery] = []
        pending_queries: list[ResearchQuery] = list(plan.queries)
        evidence: list[NormalizedEvidence] = []
        gaps: list[EvidenceGap] = []
        conflicts: list[EvidenceConflict] = []

        duplicate_count = 0
        follow_up_used = 0
        seen_query_norms = {_normalize_text(query.query) for query in pending_queries}
        seen_evidence_keys: set[str] = set()

        started = self.clock()

        while pending_queries and len(executed_queries) < plan.max_queries:
            if time_budget_seconds is not None:
                if self.clock() - started > time_budget_seconds:
                    gaps.append(
                        EvidenceGap(
                            gap_type=GapType.QUERY_FAILED,
                            query_id=None,
                            detail="Time budget exhausted before all queries completed.",
                            follow_up_allowed=False,
                        )
                    )
                    break

            query = pending_queries.pop(0)

            try:
                output = self.search_executor(query.query, max_results_per_query)
            except Exception:
                executed_queries.append(
                    ResearchQuery(
                        query_id=query.query_id,
                        query=query.query,
                        purpose=query.purpose,
                        priority=query.priority,
                        status=QueryStatus.FAILED,
                        parent_query_id=query.parent_query_id,
                    )
                )
                gaps.append(
                    EvidenceGap(
                        gap_type=GapType.QUERY_FAILED,
                        query_id=query.query_id,
                        detail="Provider failed to execute query.",
                        follow_up_allowed=(follow_up_used < plan.follow_up_budget),
                    )
                )
                continue

            executed_queries.append(
                ResearchQuery(
                    query_id=query.query_id,
                    query=query.query,
                    purpose=query.purpose,
                    priority=query.priority,
                    status=QueryStatus.EXECUTED,
                    parent_query_id=query.parent_query_id,
                )
            )

            normalized_rows = self._normalize_evidence_rows(
                query_id=query.query_id,
                rows=output.get("results", []) if isinstance(output, dict) else [],
                claim_records=claim_records,
                retrieved_from=str(output.get("provider", "web.search")) if isinstance(output, dict) else "web.search",
            )

            if not normalized_rows:
                gaps.append(
                    EvidenceGap(
                        gap_type=GapType.NO_RESULTS,
                        query_id=query.query_id,
                        detail="Query returned no usable evidence.",
                        follow_up_allowed=(follow_up_used < plan.follow_up_budget),
                    )
                )

            for item in normalized_rows:
                key = f"{_normalize_url(item.url)}|{_normalize_text(item.snippet)}"

                if key in seen_evidence_keys:
                    duplicate_count += 1
                    continue

                seen_evidence_keys.add(key)
                evidence.append(item)

            claim_gaps = _detect_claim_without_evidence(
                claim_records=claim_records,
                evidence=evidence,
            )
            gaps.extend(claim_gaps)

            diversity_gap = _detect_source_diversity_gap(evidence)
            if diversity_gap is not None:
                gaps.append(diversity_gap)

            conflicts = self._compare_evidence(evidence)
            if conflicts:
                gaps.append(
                    EvidenceGap(
                        gap_type=GapType.CONFLICT_REQUIRES_FOLLOWUP,
                        query_id=query.query_id,
                        detail="Conflicting evidence records remain unresolved.",
                        follow_up_allowed=(follow_up_used < plan.follow_up_budget),
                    )
                )

            follow_up = self._next_follow_up_query(
                plan=plan,
                executed_queries=executed_queries,
                pending_queries=pending_queries,
                gaps=gaps,
                follow_up_used=follow_up_used,
            )

            if follow_up is not None:
                normalized_follow_up = _normalize_text(follow_up.query)

                if normalized_follow_up not in seen_query_norms:
                    pending_queries.append(follow_up)
                    seen_query_norms.add(normalized_follow_up)
                    follow_up_used += 1

        sources = _build_deterministic_sources(evidence)
        status = _derive_status(evidence, executed_queries)

        return ResearchResult(
            objective=plan.objective,
            queries_executed=tuple(executed_queries),
            sources=tuple(sources),
            evidence=tuple(evidence),
            gaps=tuple(_dedupe_gaps(gaps)),
            conflicts=tuple(conflicts),
            unique_domains=len({item.domain for item in evidence if item.domain}),
            source_count=len(evidence),
            duplicate_count=duplicate_count,
            follow_up_queries_used=follow_up_used,
            status=status,
        )

    def _normalize_evidence_rows(
        self,
        query_id: str,
        rows: list[dict[str, Any]],
        claim_records: list[ResearchClaim],
        retrieved_from: str,
    ) -> list[NormalizedEvidence]:
        normalized: list[NormalizedEvidence] = []

        for rank, row in enumerate(rows, start=1):
            url = _normalize_url(str(row.get("url", "")))

            if not url.startswith(("http://", "https://")):
                continue

            title = _normalize_line(row.get("title")) or url
            snippet = _normalize_line(row.get("snippet"))
            domain = _normalize_domain(url)

            supports, contradicts = _link_claims(
                claim_records,
                title=title,
                snippet=snippet,
            )

            normalized.append(
                NormalizedEvidence(
                    evidence_id=f"{query_id}-e{rank}",
                    query_id=query_id,
                    title=title,
                    url=url,
                    domain=domain,
                    snippet=snippet,
                    source_rank=rank,
                    supports_claim_ids=tuple(sorted(set(supports))),
                    contradicts_claim_ids=tuple(sorted(set(contradicts))),
                    retrieved_from=_normalize_line(retrieved_from) or "web.search",
                )
            )

        return normalized

    def _compare_evidence(self, evidence: list[NormalizedEvidence]) -> list[EvidenceConflict]:
        conflicts: list[EvidenceConflict] = []

        for left_index in range(0, len(evidence)):
            for right_index in range(left_index + 1, len(evidence)):
                left = asdict(evidence[left_index])
                right = asdict(evidence[right_index])
                comparison = compare_evidence(
                    left,
                    right,
                    semantic_comparator=self.semantic_comparator,
                )

                if comparison.relation == ComparisonRelation.CONTRADICTS:
                    conflicts.append(
                        EvidenceConflict(
                            left_evidence_id=comparison.left_evidence_id,
                            right_evidence_id=comparison.right_evidence_id,
                            relation=comparison.relation.value,
                            reason=comparison.reason,
                        )
                    )

        return conflicts

    def _next_follow_up_query(
        self,
        plan: ResearchPlan,
        executed_queries: list[ResearchQuery],
        pending_queries: list[ResearchQuery],
        gaps: list[EvidenceGap],
        follow_up_used: int,
    ) -> ResearchQuery | None:
        if follow_up_used >= plan.follow_up_budget:
            return None

        if len(executed_queries) + len(pending_queries) >= plan.max_queries:
            return None

        for gap in reversed(gaps):
            if not gap.follow_up_allowed:
                continue

            return self.query_planner.create_follow_up_query(
                plan=plan,
                existing_queries=[*executed_queries, *pending_queries],
                gap_type=gap.gap_type.value,
                gap_detail=gap.detail,
                parent_query_id=gap.query_id,
            )

        return None


def _normalize_claims(claims: list[dict[str, Any]] | None) -> list[ResearchClaim]:
    normalized: list[ResearchClaim] = []

    for index, item in enumerate(claims or [], start=1):
        text = _normalize_line(item.get("text"))

        if not text:
            continue

        claim_id = _normalize_line(item.get("claim_id")) or f"claim-{index}"
        requires = bool(item.get("requires_evidence", True))

        normalized.append(
            ResearchClaim(
                claim_id=claim_id,
                text=text,
                requires_evidence=requires,
            )
        )

    return normalized


def _link_claims(
    claim_records: list[ResearchClaim],
    title: str,
    snippet: str,
) -> tuple[list[str], list[str]]:
    supports: list[str] = []
    contradicts: list[str] = []
    evidence_text = _normalize_text(f"{title} {snippet}")

    for claim in claim_records:
        claim_tokens = [token for token in _normalize_text(claim.text).split(" ") if len(token) >= 4]

        if not claim_tokens:
            continue

        overlap = sum(1 for token in claim_tokens if token in evidence_text)

        if overlap >= 2:
            supports.append(claim.claim_id)

        if "not" in evidence_text and overlap >= 2:
            contradicts.append(claim.claim_id)

    return supports, contradicts


def _detect_claim_without_evidence(
    claim_records: list[ResearchClaim],
    evidence: list[NormalizedEvidence],
) -> list[EvidenceGap]:
    if not claim_records:
        return []

    supported: set[str] = set()

    for item in evidence:
        for claim_id in item.supports_claim_ids:
            supported.add(claim_id)

    gaps: list[EvidenceGap] = []

    for claim in claim_records:
        if claim.requires_evidence and claim.claim_id not in supported:
            gaps.append(
                EvidenceGap(
                    gap_type=GapType.CLAIM_WITHOUT_EVIDENCE,
                    query_id=None,
                    detail=claim.text,
                    follow_up_allowed=True,
                )
            )

    return gaps


def _detect_source_diversity_gap(evidence: list[NormalizedEvidence]) -> EvidenceGap | None:
    if len(evidence) < 2:
        return None

    unique_domains = {item.domain for item in evidence if item.domain}

    if len(unique_domains) < 2:
        return EvidenceGap(
            gap_type=GapType.INSUFFICIENT_SOURCE_DIVERSITY,
            query_id=None,
            detail="Evidence currently relies on a single domain.",
            follow_up_allowed=True,
        )

    return None


def _build_deterministic_sources(evidence: list[NormalizedEvidence]) -> list[dict[str, Any]]:
    ordered = sorted(
        evidence,
        key=lambda item: (item.query_id, item.source_rank, item.url),
    )

    sources: list[dict[str, Any]] = []

    for index, item in enumerate(ordered, start=1):
        sources.append(
            {
                "number": index,
                "title": item.title,
                "url": item.url,
                "source": item.domain,
                "query_id": item.query_id,
                "evidence_id": item.evidence_id,
                "supports_claim_ids": list(item.supports_claim_ids),
                "contradicts_claim_ids": list(item.contradicts_claim_ids),
            }
        )

    return sources


def _derive_status(
    evidence: list[NormalizedEvidence],
    queries: list[ResearchQuery],
) -> ResearchStatus:
    if not evidence:
        return ResearchStatus.FAILED

    if any(query.status == QueryStatus.FAILED for query in queries):
        return ResearchStatus.PARTIAL

    return ResearchStatus.COMPLETE


def _dedupe_gaps(gaps: list[EvidenceGap]) -> list[EvidenceGap]:
    deduped: list[EvidenceGap] = []
    seen: set[str] = set()

    for item in gaps:
        key = f"{item.gap_type.value}|{item.query_id}|{item.detail}"

        if key in seen:
            continue

        seen.add(key)
        deduped.append(item)

    return deduped


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _normalize_line(value: Any) -> str:
    return " ".join(str(value or "").split())


def _normalize_url(value: str) -> str:
    text = _normalize_line(value).strip()

    if not text:
        return ""

    parts = urlparse(text)

    if not parts.scheme or not parts.netloc:
        return text.lower()

    path = parts.path.rstrip("/")
    normalized = f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}"

    if parts.query:
        normalized = f"{normalized}?{parts.query}"

    return normalized


def _normalize_domain(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""
