from dataclasses import dataclass
from enum import Enum


DEFAULT_MAX_QUERIES = 4
DEFAULT_FOLLOW_UP_BUDGET = 2
HARD_MAX_QUERIES = 8
HARD_MAX_FOLLOW_UP_BUDGET = 4


class QueryStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class ResearchQuery:
    query_id: str
    query: str
    purpose: str
    priority: int
    status: QueryStatus = QueryStatus.PENDING
    parent_query_id: str | None = None

    def __post_init__(self):
        if not self.query_id.strip():
            raise ValueError("query_id cannot be empty")

        if not _normalize_query_text(self.query):
            raise ValueError("query cannot be empty")

        if self.priority < 1:
            raise ValueError("priority must be >= 1")


@dataclass(frozen=True)
class ResearchPlan:
    objective: str
    queries: tuple[ResearchQuery, ...]
    max_queries: int = DEFAULT_MAX_QUERIES
    follow_up_budget: int = DEFAULT_FOLLOW_UP_BUDGET

    def __post_init__(self):
        clean_objective = self.objective.strip()

        if not clean_objective:
            raise ValueError("objective cannot be empty")

        if self.max_queries < 1 or self.max_queries > HARD_MAX_QUERIES:
            raise ValueError("max_queries is outside hard limits")

        if self.follow_up_budget < 0 or self.follow_up_budget > HARD_MAX_FOLLOW_UP_BUDGET:
            raise ValueError("follow_up_budget is outside hard limits")

        if len(self.queries) > self.max_queries:
            raise ValueError("query count exceeds max_queries")

        _validate_unique_queries(self.queries)


class QueryPlanner:
    """Deterministic bounded planner for research query plans."""

    def __init__(
        self,
        default_max_queries: int = DEFAULT_MAX_QUERIES,
        default_follow_up_budget: int = DEFAULT_FOLLOW_UP_BUDGET,
        hard_max_queries: int = HARD_MAX_QUERIES,
        hard_follow_up_budget: int = HARD_MAX_FOLLOW_UP_BUDGET,
    ):
        self.default_max_queries = default_max_queries
        self.default_follow_up_budget = default_follow_up_budget
        self.hard_max_queries = hard_max_queries
        self.hard_follow_up_budget = hard_follow_up_budget

    def create_plan(
        self,
        objective: str,
        seed_queries: list[str] | None = None,
        max_queries: int | None = None,
        follow_up_budget: int | None = None,
    ) -> ResearchPlan:
        clean_objective = objective.strip()

        if not clean_objective:
            raise ValueError("objective cannot be empty")

        bounded_max_queries = self._bounded_max_queries(max_queries)
        bounded_follow_up = self._bounded_follow_up_budget(follow_up_budget)

        raw_queries = list(seed_queries or [])

        if not raw_queries:
            raw_queries = _default_seed_queries(clean_objective)

        queries: list[ResearchQuery] = []
        seen: set[str] = set()

        for index, raw_query in enumerate(raw_queries, start=1):
            normalized = _normalize_query_text(raw_query)

            if not normalized:
                raise ValueError("seed query cannot be empty")

            if normalized in seen:
                continue

            seen.add(normalized)

            if len(queries) >= bounded_max_queries:
                raise ValueError("seed queries exceed max_queries")

            queries.append(
                ResearchQuery(
                    query_id=f"q-{index}",
                    query=raw_query.strip(),
                    purpose="Collect baseline evidence",
                    priority=index,
                )
            )

        if not queries:
            raise ValueError("query plan cannot be empty")

        return ResearchPlan(
            objective=clean_objective,
            queries=tuple(queries),
            max_queries=bounded_max_queries,
            follow_up_budget=bounded_follow_up,
        )

    def create_follow_up_query(
        self,
        plan: ResearchPlan,
        existing_queries: list[ResearchQuery],
        gap_type: str,
        gap_detail: str,
        parent_query_id: str | None,
    ) -> ResearchQuery | None:
        if len(existing_queries) >= plan.max_queries:
            return None

        normalized_existing = {
            _normalize_query_text(item.query)
            for item in existing_queries
        }

        candidate = _build_follow_up_query(plan.objective, gap_type, gap_detail)
        normalized_candidate = _normalize_query_text(candidate)

        if not normalized_candidate:
            return None

        if normalized_candidate in normalized_existing:
            return None

        next_priority = len(existing_queries) + 1

        return ResearchQuery(
            query_id=f"q-{next_priority}",
            query=candidate,
            purpose=f"Follow-up for {gap_type}",
            priority=next_priority,
            parent_query_id=parent_query_id,
        )

    def _bounded_max_queries(self, value: int | None) -> int:
        candidate = self.default_max_queries if value is None else int(value)

        if candidate < 1 or candidate > self.hard_max_queries:
            raise ValueError("max_queries is outside hard limits")

        return candidate

    def _bounded_follow_up_budget(self, value: int | None) -> int:
        candidate = self.default_follow_up_budget if value is None else int(value)

        if candidate < 0 or candidate > self.hard_follow_up_budget:
            raise ValueError("follow_up_budget is outside hard limits")

        return candidate


def _normalize_query_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _validate_unique_queries(queries: tuple[ResearchQuery, ...]):
    seen: set[str] = set()

    for query in queries:
        normalized = _normalize_query_text(query.query)

        if not normalized:
            raise ValueError("query cannot be empty")

        if normalized in seen:
            raise ValueError("duplicate normalized query is not allowed")

        seen.add(normalized)


def _default_seed_queries(objective: str) -> list[str]:
    # Deterministic conservative expansion: one direct query plus one scoped context query.
    base = objective.strip()
    scoped = f"official source {base}"

    if _normalize_query_text(base) == _normalize_query_text(scoped):
        return [base]

    return [base, scoped]


def _build_follow_up_query(objective: str, gap_type: str, gap_detail: str) -> str:
    short_detail = " ".join(str(gap_detail or "").split())

    if gap_type == "NO_RESULTS":
        return f"latest official information {objective}".strip()

    if gap_type == "INSUFFICIENT_SOURCE_DIVERSITY":
        return f"independent source verification {objective}".strip()

    if gap_type == "CONFLICT_REQUIRES_FOLLOWUP":
        return f"resolve conflicting sources {objective}".strip()

    if gap_type == "CLAIM_WITHOUT_EVIDENCE":
        return f"evidence for claim {short_detail}".strip()

    if gap_type == "QUERY_FAILED":
        return f"alternative source for {objective}".strip()

    return f"additional evidence {objective}".strip()
