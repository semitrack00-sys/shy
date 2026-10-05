from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover - dependency is expected in runtime
    psycopg = None
    dict_row = None

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://shy:shy_local_dev@127.0.0.1:5432/shy",
)


def connect() -> Any:
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg unavailable")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def ensure_knowledge_schema() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_records (
                    knowledge_id UUID PRIMARY KEY,
                    user_id UUID NOT NULL,
                    workspace_id TEXT NOT NULL,
                    business_id TEXT,
                    allow_public BOOLEAN NOT NULL DEFAULT FALSE,
                    subject TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    normalized_content TEXT NOT NULL,
                    source_title TEXT,
                    source_timestamp TIMESTAMPTZ,
                    observed_at TIMESTAMPTZ NOT NULL,
                    effective_from TIMESTAMPTZ,
                    effective_to TIMESTAMPTZ,
                    confidence REAL NOT NULL,
                    freshness TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provenance_source_type TEXT NOT NULL,
                    provenance_source_id TEXT NOT NULL,
                    provenance_source_title TEXT,
                    provenance_source_timestamp TIMESTAMPTZ,
                    provenance_authority TEXT NOT NULL,
                    provenance_retrieved_at TIMESTAMPTZ NOT NULL,
                    provenance_content_hash TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE knowledge_records
                ADD COLUMN IF NOT EXISTS business_key TEXT GENERATED ALWAYS AS (COALESCE(business_id, '')) STORED
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    knowledge_id UUID NOT NULL REFERENCES knowledge_records(knowledge_id) ON DELETE CASCADE,
                    order_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    normalized_content TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_relationships (
                    relationship_id UUID PRIMARY KEY,
                    knowledge_id UUID NOT NULL REFERENCES knowledge_records(knowledge_id) ON DELETE CASCADE,
                    related_knowledge_id UUID NOT NULL REFERENCES knowledge_records(knowledge_id) ON DELETE CASCADE,
                    relationship_type TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (knowledge_id, related_knowledge_id, relationship_type)
                )
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_records_dedupe_key
                ON knowledge_records (user_id, workspace_id, business_key, allow_public, subject, source_id, content_hash)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_records_scope_order
                ON knowledge_records (user_id, workspace_id, business_key, updated_at DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_records_subject
                ON knowledge_records (user_id, workspace_id, business_key, subject)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_records_source_id
                ON knowledge_records (user_id, workspace_id, business_key, source_id)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_records_content_hash
                ON knowledge_records (user_id, workspace_id, business_key, content_hash)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_records_scope_status
                ON knowledge_records (user_id, workspace_id, business_key, status)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_records_freshness_updated
                ON knowledge_records (user_id, workspace_id, business_key, freshness, updated_at DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_knowledge
                ON knowledge_chunks (knowledge_id, order_index)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_relationships_knowledge_id
                ON knowledge_relationships (knowledge_id, relationship_type)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_relationships_related_id
                ON knowledge_relationships (related_knowledge_id, relationship_type)
                """
            )


class KnowledgeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    ARCHIVED = "ARCHIVED"
    UNAVAILABLE = "UNAVAILABLE"


class KnowledgeSourceType(str, Enum):
    USER = "USER"
    MEMORY = "MEMORY"
    DOCUMENT = "DOCUMENT"
    DATABASE = "DATABASE"
    TOOL = "TOOL"
    RESEARCH = "RESEARCH"
    SYSTEM = "SYSTEM"
    VERIFIED_DERIVATION = "VERIFIED_DERIVATION"


class KnowledgeFreshness(str, Enum):
    CURRENT = "CURRENT"
    AGING = "AGING"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class AuthorityLevel(str, Enum):
    PRIMARY = "PRIMARY"
    AUTHORITATIVE = "AUTHORITATIVE"
    TRUSTED = "TRUSTED"
    USER_PROVIDED = "USER_PROVIDED"
    SECONDARY = "SECONDARY"
    UNVERIFIED = "UNVERIFIED"


class KnowledgeSensitivity(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"
    SECRET = "SECRET"


class KnowledgeBoundary(str, Enum):
    KNOWLEDGE_AVAILABLE = "KNOWLEDGE_AVAILABLE"
    RETRIEVAL_REQUIRED = "RETRIEVAL_REQUIRED"
    RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
    DATA_REQUIRED = "DATA_REQUIRED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    CONFLICTING_KNOWLEDGE = "CONFLICTING_KNOWLEDGE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class GroundingStatus(str, Enum):
    GROUNDED = "GROUNDED"
    PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
    UNGROUNDED = "UNGROUNDED"
    CONFLICTED = "CONFLICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class KnowledgeScope:
    user_id: uuid.UUID
    workspace_id: str
    business_id: str | None = None
    allow_public: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", uuid.UUID(str(self.user_id)))


@dataclass(frozen=True)
class KnowledgeProvenance:
    source_type: KnowledgeSourceType
    source_id: str
    source_title: str | None
    source_timestamp: datetime | None
    authority: AuthorityLevel
    retrieved_at: datetime
    content_hash: str


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    order_index: int
    content: str
    normalized_content: str
    content_hash: str


@dataclass(frozen=True)
class KnowledgeRecord:
    knowledge_id: uuid.UUID
    scope: KnowledgeScope
    source_type: KnowledgeSourceType
    source_id: str
    subject: str
    content: str
    normalized_content: str
    source_title: str | None
    source_timestamp: datetime | None
    observed_at: datetime
    effective_from: datetime | None
    effective_to: datetime | None
    confidence: float
    freshness: KnowledgeFreshness
    authority: AuthorityLevel
    sensitivity: KnowledgeSensitivity
    status: KnowledgeStatus
    provenance: KnowledgeProvenance
    content_hash: str
    created_at: datetime
    updated_at: datetime
    chunks: tuple[KnowledgeChunk, ...]


@dataclass(frozen=True)
class KnowledgeCitation:
    citation_id: str
    knowledge_id: uuid.UUID
    source_type: KnowledgeSourceType
    source_id: str
    title: str | None
    source_timestamp: datetime | None


@dataclass(frozen=True)
class KnowledgeConflict:
    subject: str
    knowledge_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class KnowledgeIngestionResult:
    accepted: bool
    rejected_reason: str | None
    created: tuple[KnowledgeRecord, ...]
    duplicate_of: uuid.UUID | None


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    records: tuple[KnowledgeRecord, ...]
    citations: tuple[KnowledgeCitation, ...]
    conflicts: tuple[KnowledgeConflict, ...]
    knowledge_boundary: KnowledgeBoundary
    grounding_status: GroundingStatus
    candidates_considered: int
    context_chars: int
    truncated_by_limit: bool
    truncated_by_budget: bool
    source_count: int
    authoritative_source_count: int
    stale_source_count: int


_SECRET_MARKERS = (
    "password",
    "passwd",
    "api key",
    "api_key",
    "access token",
    "oauth",
    "approval token",
    "bearer",
    "private key",
    "secret",
    "database_url",
    "env dump",
    "chain-of-thought",
    "hidden reasoning",
    "verifier reasoning",
)

_STOPWORDS = {
    "the",
    "is",
    "are",
    "a",
    "an",
    "of",
    "to",
    "for",
    "and",
    "or",
    "in",
    "on",
    "at",
    "with",
    "what",
    "which",
    "who",
    "how",
    "does",
    "do",
    "did",
    "be",
    "it",
    "its",
    "this",
    "that",
}


_AUTHORITY_WEIGHTS = {
    AuthorityLevel.PRIMARY: 1.0,
    AuthorityLevel.AUTHORITATIVE: 0.9,
    AuthorityLevel.TRUSTED: 0.8,
    AuthorityLevel.USER_PROVIDED: 0.65,
    AuthorityLevel.SECONDARY: 0.5,
    AuthorityLevel.UNVERIFIED: 0.35,
}


_STATUS_WEIGHTS = {
    KnowledgeStatus.ACTIVE: 0.1,
    KnowledgeStatus.STALE: -0.15,
    KnowledgeStatus.CONFLICTED: -0.2,
    KnowledgeStatus.SUPERSEDED: -0.45,
    KnowledgeStatus.ARCHIVED: -0.5,
    KnowledgeStatus.UNAVAILABLE: -0.6,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _tokenize(value: str) -> tuple[str, ...]:
    tokens = re.findall(r"[a-z0-9_]+", _normalize_text(value))
    return tuple(token for token in tokens if len(token) >= 2 and token not in _STOPWORDS)


def _contains_secret_like_content(value: str) -> bool:
    lowered = _normalize_text(value)
    if "sk-" in lowered:
        return True
    if re.search(r"\b[a-z0-9_\-]*token\b\s*[:=]", lowered):
        return True
    return any(marker in lowered for marker in _SECRET_MARKERS)


def _subject_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_.-]+", ".", _normalize_text(value))
    cleaned = cleaned.strip(".")
    return cleaned or "general"


def _bounded_content(value: str, max_chars: int = 1600) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _content_hash(scope: KnowledgeScope, subject: str, normalized_content: str, source_id: str) -> str:
    payload = "|".join(
        (
            str(scope.user_id),
            scope.workspace_id,
            str(scope.business_id or ""),
            subject,
            source_id,
            normalized_content,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _freshness_from_timestamps(source_type: KnowledgeSourceType, source_timestamp: datetime | None, observed_at: datetime) -> KnowledgeFreshness:
    if source_timestamp is None:
        return KnowledgeFreshness.UNKNOWN

    age_days = max(0.0, (observed_at - source_timestamp).total_seconds() / 86400.0)
    thresholds = {
        KnowledgeSourceType.DATABASE: (7.0, 30.0),
        KnowledgeSourceType.TOOL: (7.0, 30.0),
        KnowledgeSourceType.RESEARCH: (14.0, 60.0),
        KnowledgeSourceType.DOCUMENT: (30.0, 180.0),
        KnowledgeSourceType.MEMORY: (30.0, 180.0),
        KnowledgeSourceType.USER: (90.0, 365.0),
        KnowledgeSourceType.SYSTEM: (30.0, 180.0),
        KnowledgeSourceType.VERIFIED_DERIVATION: (14.0, 90.0),
    }
    aging_threshold, stale_threshold = thresholds.get(source_type, (30.0, 120.0))
    if age_days <= aging_threshold:
        return KnowledgeFreshness.CURRENT
    if age_days <= stale_threshold:
        return KnowledgeFreshness.AGING
    return KnowledgeFreshness.STALE


def _split_chunks(text: str, max_chunk_chars: int, overlap_chars: int) -> tuple[tuple[str, int], ...]:
    normalized = _bounded_content(text, max_chars=64000)
    if not normalized:
        return ()

    if max_chunk_chars < 64:
        max_chunk_chars = 64
    if overlap_chars < 0:
        overlap_chars = 0
    if overlap_chars >= max_chunk_chars:
        overlap_chars = max_chunk_chars // 4

    output: list[tuple[str, int]] = []
    start = 0
    length = len(normalized)
    while start < length:
        end = min(length, start + max_chunk_chars)
        if end < length:
            split = normalized.rfind(" ", start, end)
            if split > start + 32:
                end = split
        chunk = normalized[start:end].strip()
        if chunk:
            output.append((chunk, len(output)))
        if end >= length:
            break
        start = max(0, end - overlap_chars)
    return tuple(output)


def _near_duplicate(a: str, b: str) -> bool:
    tokens_a = set(_tokenize(a))
    tokens_b = set(_tokenize(b))
    if not tokens_a or not tokens_b:
        return False
    intersect = len(tokens_a.intersection(tokens_b))
    union = len(tokens_a.union(tokens_b))
    if union == 0:
        return False
    similarity = intersect / union
    return similarity >= 0.96


def _scope_specificity(target: KnowledgeScope, candidate: KnowledgeScope) -> float:
    if target.user_id != candidate.user_id:
        return -10.0
    score = 0.0
    if target.workspace_id == candidate.workspace_id:
        score += 0.16
    if (target.business_id or "") == (candidate.business_id or ""):
        score += 0.1
    if candidate.allow_public:
        score -= 0.05
    return score


def _source_is_authoritative(authority: AuthorityLevel) -> bool:
    return authority in {AuthorityLevel.PRIMARY, AuthorityLevel.AUTHORITATIVE, AuthorityLevel.TRUSTED}


class PostgresKnowledgeStore:
    def __init__(
        self,
        *,
        max_chunk_chars: int = 320,
        overlap_chars: int = 48,
        max_retrieval_results: int = 8,
        max_context_chars: int = 2600,
        max_sources: int = 8,
        max_chunks: int = 24,
    ):
        self._records: dict[uuid.UUID, KnowledgeRecord] = {}
        self._max_chunk_chars = max_chunk_chars
        self._overlap_chars = overlap_chars
        self._max_retrieval_results = max_retrieval_results
        self._max_context_chars = max_context_chars
        self._max_sources = max_sources
        self._max_chunks = max_chunks
        ensure_knowledge_schema()
        self._refresh_cache()

    def _refresh_cache(self) -> None:
        self._records = {}
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM knowledge_records
                    ORDER BY updated_at DESC, knowledge_id
                    """
                )
                rows = cur.fetchall()
                if not rows:
                    return

                cur.execute(
                    "SELECT * FROM knowledge_chunks ORDER BY knowledge_id, order_index"
                )
                chunks_by_record: dict[str, list[KnowledgeChunk]] = {}
                for chunk_row in cur.fetchall():
                    record_id = str(chunk_row["knowledge_id"])
                    chunks_by_record.setdefault(record_id, []).append(
                        KnowledgeChunk(
                            chunk_id=chunk_row["chunk_id"],
                            order_index=int(chunk_row["order_index"]),
                            content=chunk_row["content"],
                            normalized_content=chunk_row["normalized_content"],
                            content_hash=chunk_row["content_hash"],
                        )
                    )

                for row in rows:
                    record_id = uuid.UUID(str(row["knowledge_id"]))
                    scope = KnowledgeScope(
                        user_id=row["user_id"],
                        workspace_id=row["workspace_id"],
                        business_id=row["business_id"],
                        allow_public=bool(row["allow_public"]),
                    )
                    provenance = KnowledgeProvenance(
                        source_type=KnowledgeSourceType(row["provenance_source_type"]),
                        source_id=row["provenance_source_id"],
                        source_title=row["provenance_source_title"],
                        source_timestamp=row["provenance_source_timestamp"],
                        authority=AuthorityLevel(row["provenance_authority"]),
                        retrieved_at=row["provenance_retrieved_at"],
                        content_hash=row["provenance_content_hash"],
                    )
                    record = KnowledgeRecord(
                        knowledge_id=record_id,
                        scope=scope,
                        source_type=KnowledgeSourceType(row["source_type"]),
                        source_id=row["source_id"],
                        subject=row["subject"],
                        content=row["content"],
                        normalized_content=row["normalized_content"],
                        source_title=row["source_title"],
                        source_timestamp=row["source_timestamp"],
                        observed_at=row["observed_at"],
                        effective_from=row["effective_from"],
                        effective_to=row["effective_to"],
                        confidence=float(row["confidence"]),
                        freshness=KnowledgeFreshness(row["freshness"]),
                        authority=AuthorityLevel(row["authority"]),
                        sensitivity=KnowledgeSensitivity(row["sensitivity"]),
                        status=KnowledgeStatus(row["status"]),
                        provenance=provenance,
                        content_hash=row["content_hash"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        chunks=tuple(chunks_by_record.get(str(record_id), ())),
                    )
                    self._records[record_id] = record

    def _persist_snapshot(self) -> None:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM knowledge_relationships")
                cur.execute("DELETE FROM knowledge_chunks")
                cur.execute("DELETE FROM knowledge_records")

                for record in sorted(self._records.values(), key=lambda row: (row.updated_at, str(row.knowledge_id)), reverse=True):
                    cur.execute(
                        """
                        INSERT INTO knowledge_records (
                            knowledge_id, user_id, workspace_id, business_id, allow_public,
                            subject, source_type, source_id, content, normalized_content,
                            source_title, source_timestamp, observed_at, effective_from, effective_to,
                            confidence, freshness, authority, sensitivity, status,
                            provenance_source_type, provenance_source_id, provenance_source_title,
                            provenance_source_timestamp, provenance_authority, provenance_retrieved_at,
                            provenance_content_hash, content_hash, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            record.knowledge_id,
                            record.scope.user_id,
                            record.scope.workspace_id,
                            record.scope.business_id,
                            record.scope.allow_public,
                            record.subject,
                            record.source_type.value,
                            record.source_id,
                            record.content,
                            record.normalized_content,
                            record.source_title,
                            record.source_timestamp,
                            record.observed_at,
                            record.effective_from,
                            record.effective_to,
                            float(record.confidence),
                            record.freshness.value,
                            record.authority.value,
                            record.sensitivity.value,
                            record.status.value,
                            record.provenance.source_type.value,
                            record.provenance.source_id,
                            record.provenance.source_title,
                            record.provenance.source_timestamp,
                            record.provenance.authority.value,
                            record.provenance.retrieved_at,
                            record.provenance.content_hash,
                            record.content_hash,
                            record.created_at,
                            record.updated_at,
                        ),
                    )
                    for chunk in record.chunks:
                        cur.execute(
                            """
                            INSERT INTO knowledge_chunks (
                                chunk_id, knowledge_id, order_index, content,
                                normalized_content, content_hash
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                chunk.chunk_id,
                                record.knowledge_id,
                                chunk.order_index,
                                chunk.content,
                                chunk.normalized_content,
                                chunk.content_hash,
                            ),
                        )

    def list_records(self, scope: KnowledgeScope | None = None) -> list[KnowledgeRecord]:
        self._refresh_cache()
        return InMemoryKnowledgeStore.list_records(self, scope)

    def get_record(self, knowledge_id: uuid.UUID) -> KnowledgeRecord | None:
        self._refresh_cache()
        return InMemoryKnowledgeStore.get_record(self, knowledge_id)

    def _scope_visible(self, query_scope: KnowledgeScope, record_scope: KnowledgeScope) -> bool:
        return InMemoryKnowledgeStore._scope_visible(self, query_scope, record_scope)

    def _ranking_score(
        self,
        query_tokens: tuple[str, ...],
        record: KnowledgeRecord,
        target_scope: KnowledgeScope,
        now: datetime,
    ) -> float:
        return InMemoryKnowledgeStore._ranking_score(self, query_tokens, record, target_scope, now)

    def _detect_conflicts(self, rows: list[KnowledgeRecord]) -> tuple[KnowledgeConflict, ...]:
        return InMemoryKnowledgeStore._detect_conflicts(self, rows)

    def _knowledge_boundary(
        self,
        rows: list[KnowledgeRecord],
        conflicts: tuple[KnowledgeConflict, ...],
        *,
        requires_external_research: bool,
        dependency_unavailable: bool,
    ) -> KnowledgeBoundary:
        return InMemoryKnowledgeStore._knowledge_boundary(
            self,
            rows,
            conflicts,
            requires_external_research=requires_external_research,
            dependency_unavailable=dependency_unavailable,
        )

    def _grounding_status(
        self,
        rows: list[KnowledgeRecord],
        conflicts: tuple[KnowledgeConflict, ...],
    ) -> GroundingStatus:
        return InMemoryKnowledgeStore._grounding_status(self, rows, conflicts)

    def reset(self) -> None:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM knowledge_relationships")
                cur.execute("DELETE FROM knowledge_chunks")
                cur.execute("DELETE FROM knowledge_records")
        self._records = {}

    def ingest_text(
        self,
        *,
        scope: KnowledgeScope,
        source_type: KnowledgeSourceType,
        source_id: str,
        subject: str,
        content: str,
        source_title: str | None = None,
        source_timestamp: datetime | None = None,
        observed_at: datetime | None = None,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        confidence: float = 0.7,
        authority: AuthorityLevel = AuthorityLevel.USER_PROVIDED,
        sensitivity: KnowledgeSensitivity = KnowledgeSensitivity.INTERNAL,
        correction: bool = False,
    ) -> KnowledgeIngestionResult:
        self._refresh_cache()
        before = set(self._records)
        result = InMemoryKnowledgeStore.ingest_text(
            self,
            scope=scope,
            source_type=source_type,
            source_id=source_id,
            subject=subject,
            content=content,
            source_title=source_title,
            source_timestamp=source_timestamp,
            observed_at=observed_at,
            effective_from=effective_from,
            effective_to=effective_to,
            confidence=confidence,
            authority=authority,
            sensitivity=sensitivity,
            correction=correction,
        )
        if result.accepted and result.created:
            created = result.created[0]
            with connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO knowledge_records (
                            knowledge_id, user_id, workspace_id, business_id, allow_public,
                            subject, source_type, source_id, content, normalized_content,
                            source_title, source_timestamp, observed_at, effective_from, effective_to,
                            confidence, freshness, authority, sensitivity, status,
                            provenance_source_type, provenance_source_id, provenance_source_title,
                            provenance_source_timestamp, provenance_authority, provenance_retrieved_at,
                            provenance_content_hash, content_hash, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id, workspace_id, business_key, allow_public, subject, source_id, content_hash) DO NOTHING
                        RETURNING knowledge_id
                        """,
                        (
                            created.knowledge_id,
                            created.scope.user_id,
                            created.scope.workspace_id,
                            created.scope.business_id,
                            created.scope.allow_public,
                            created.subject,
                            created.source_type.value,
                            created.source_id,
                            created.content,
                            created.normalized_content,
                            created.source_title,
                            created.source_timestamp,
                            created.observed_at,
                            created.effective_from,
                            created.effective_to,
                            float(created.confidence),
                            created.freshness.value,
                            created.authority.value,
                            created.sensitivity.value,
                            created.status.value,
                            created.provenance.source_type.value,
                            created.provenance.source_id,
                            created.provenance.source_title,
                            created.provenance.source_timestamp,
                            created.provenance.authority.value,
                            created.provenance.retrieved_at,
                            created.provenance.content_hash,
                            created.content_hash,
                            created.created_at,
                            created.updated_at,
                        ),
                    )
                    inserted = cur.fetchone()
                    if inserted is not None:
                        for chunk in created.chunks:
                            cur.execute(
                                """
                                INSERT INTO knowledge_chunks (
                                    chunk_id, knowledge_id, order_index, content,
                                    normalized_content, content_hash
                                ) VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (chunk_id) DO NOTHING
                                """,
                                (
                                    chunk.chunk_id,
                                    created.knowledge_id,
                                    chunk.order_index,
                                    chunk.content,
                                    chunk.normalized_content,
                                    chunk.content_hash,
                                ),
                            )
                    else:
                        cur.execute(
                            """
                            SELECT knowledge_id
                            FROM knowledge_records
                            WHERE user_id=%s AND workspace_id=%s AND COALESCE(business_id, '')=%s
                              AND allow_public=%s AND subject=%s AND source_id=%s AND content_hash=%s
                            ORDER BY updated_at DESC
                            LIMIT 1
                            """,
                            (
                                created.scope.user_id,
                                created.scope.workspace_id,
                                created.scope.business_id or "",
                                created.scope.allow_public,
                                created.subject,
                                created.source_id,
                                created.content_hash,
                            ),
                        )
                        duplicate = cur.fetchone()
                        if duplicate is not None:
                            result = KnowledgeIngestionResult(
                                True,
                                None,
                                (),
                                uuid.UUID(str(duplicate["knowledge_id"])),
                            )

            if correction:
                created_ids = set(self._records) - before
                superseded_ids = [record_id for record_id in before if record_id in self._records and self._records[record_id].status == KnowledgeStatus.SUPERSEDED]
                for old_id in superseded_ids:
                    old_record = self._records.get(old_id)
                    if old_record is None:
                        continue
                    new_id = next(iter(created_ids), None)
                    with connect() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                UPDATE knowledge_records
                                SET status = %s,
                                    effective_to = %s,
                                    updated_at = %s
                                WHERE knowledge_id = %s
                                """,
                                (
                                    old_record.status.value,
                                    old_record.effective_to,
                                    old_record.updated_at,
                                    old_id,
                                ),
                            )
                            if new_id is not None:
                                cur.execute(
                                    """
                                    INSERT INTO knowledge_relationships (relationship_id, knowledge_id, related_knowledge_id, relationship_type)
                                    VALUES (%s, %s, %s, %s)
                                    ON CONFLICT (knowledge_id, related_knowledge_id, relationship_type) DO NOTHING
                                    """,
                                    (uuid.uuid4(), old_id, new_id, "SUPERSEDED_BY"),
                                )
        self._refresh_cache()
        return result

    def ingest_structured_record(
        self,
        *,
        scope: KnowledgeScope,
        source_type: KnowledgeSourceType,
        source_id: str,
        subject: str,
        record: dict[str, Any],
        source_title: str | None = None,
        source_timestamp: datetime | None = None,
        authority: AuthorityLevel = AuthorityLevel.TRUSTED,
        confidence: float = 0.75,
    ) -> KnowledgeIngestionResult:
        return self.ingest_text(
            scope=scope,
            source_type=source_type,
            source_id=source_id,
            subject=subject,
            content="; ".join(f"{key}={record[key]}" for key in sorted(record.keys())),
            source_title=source_title,
            source_timestamp=source_timestamp,
            authority=authority,
            confidence=confidence,
        )

    def ingest_memory_record(
        self,
        *,
        scope: KnowledgeScope,
        source_id: str,
        subject: str,
        content: str,
        source_title: str | None = None,
        confidence: float = 0.68,
    ) -> KnowledgeIngestionResult:
        return self.ingest_text(
            scope=scope,
            source_type=KnowledgeSourceType.MEMORY,
            source_id=source_id,
            subject=subject,
            content=content,
            source_title=source_title,
            authority=AuthorityLevel.USER_PROVIDED,
            confidence=confidence,
        )

    def ingest_tool_output(
        self,
        *,
        scope: KnowledgeScope,
        tool_name: str,
        source_id: str,
        subject: str,
        output: dict[str, Any],
        source_timestamp: datetime | None = None,
        confidence: float = 0.8,
    ) -> KnowledgeIngestionResult:
        flattened = "; ".join(f"{key}={output[key]}" for key in sorted(output.keys()))
        return self.ingest_text(
            scope=scope,
            source_type=KnowledgeSourceType.TOOL,
            source_id=source_id,
            subject=subject,
            content=flattened,
            source_title=tool_name,
            source_timestamp=source_timestamp,
            authority=AuthorityLevel.AUTHORITATIVE,
            confidence=confidence,
        )

    def retrieve(
        self,
        *,
        query_text: str,
        scope: KnowledgeScope,
        max_results: int | None = None,
        max_context_chars: int | None = None,
        max_sources: int | None = None,
        require_authoritative: bool = False,
        requires_external_research: bool = False,
        dependency_unavailable: bool = False,
    ) -> KnowledgeRetrievalResult:
        self._refresh_cache()
        return InMemoryKnowledgeStore.retrieve(
            self,
            query_text=query_text,
            scope=scope,
            max_results=max_results,
            max_context_chars=max_context_chars,
            max_sources=max_sources,
            require_authoritative=require_authoritative,
            requires_external_research=requires_external_research,
            dependency_unavailable=dependency_unavailable,
        )


class InMemoryKnowledgeStore:
    def __init__(
        self,
        *,
        max_chunk_chars: int = 320,
        overlap_chars: int = 48,
        max_retrieval_results: int = 8,
        max_context_chars: int = 2600,
        max_sources: int = 8,
        max_chunks: int = 24,
    ):
        self._records: dict[uuid.UUID, KnowledgeRecord] = {}
        self._max_chunk_chars = max_chunk_chars
        self._overlap_chars = overlap_chars
        self._max_retrieval_results = max_retrieval_results
        self._max_context_chars = max_context_chars
        self._max_sources = max_sources
        self._max_chunks = max_chunks

    def list_records(self, scope: KnowledgeScope | None = None) -> list[KnowledgeRecord]:
        rows = list(self._records.values())
        if scope is not None:
            rows = [row for row in rows if self._scope_visible(scope, row.scope)]
        rows.sort(key=lambda row: (row.updated_at, str(row.knowledge_id)), reverse=True)
        return rows

    def get_record(self, knowledge_id: uuid.UUID) -> KnowledgeRecord | None:
        return self._records.get(knowledge_id)

    def reset(self) -> None:
        self._records = {}

    def ingest_text(
        self,
        *,
        scope: KnowledgeScope,
        source_type: KnowledgeSourceType,
        source_id: str,
        subject: str,
        content: str,
        source_title: str | None = None,
        source_timestamp: datetime | None = None,
        observed_at: datetime | None = None,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        confidence: float = 0.7,
        authority: AuthorityLevel = AuthorityLevel.USER_PROVIDED,
        sensitivity: KnowledgeSensitivity = KnowledgeSensitivity.INTERNAL,
        correction: bool = False,
    ) -> KnowledgeIngestionResult:
        bounded_content = _bounded_content(content)
        if not bounded_content:
            return KnowledgeIngestionResult(False, "EMPTY_CONTENT", (), None)

        if _contains_secret_like_content(bounded_content):
            return KnowledgeIngestionResult(False, "SENSITIVE_CONTENT", (), None)

        normalized_subject = _subject_key(subject)
        normalized_content = _normalize_text(bounded_content)
        canonical_source_id = str(source_id or "unknown")
        observed = observed_at or _utcnow()
        content_hash = _content_hash(scope, normalized_subject, normalized_content, canonical_source_id)

        # Exact duplicate prevention.
        for existing in self._records.values():
            if (
                existing.scope == scope
                and existing.subject == normalized_subject
                and existing.content_hash == content_hash
                and existing.status == KnowledgeStatus.ACTIVE
            ):
                refreshed = KnowledgeRecord(
                    knowledge_id=existing.knowledge_id,
                    scope=existing.scope,
                    source_type=existing.source_type,
                    source_id=existing.source_id,
                    subject=existing.subject,
                    content=existing.content,
                    normalized_content=existing.normalized_content,
                    source_title=existing.source_title,
                    source_timestamp=existing.source_timestamp,
                    observed_at=observed,
                    effective_from=existing.effective_from,
                    effective_to=existing.effective_to,
                    confidence=max(existing.confidence, confidence),
                    freshness=_freshness_from_timestamps(existing.source_type, existing.source_timestamp, observed),
                    authority=existing.authority,
                    sensitivity=existing.sensitivity,
                    status=existing.status,
                    provenance=KnowledgeProvenance(
                        source_type=existing.source_type,
                        source_id=existing.source_id,
                        source_title=existing.source_title,
                        source_timestamp=existing.source_timestamp,
                        authority=existing.authority,
                        retrieved_at=observed,
                        content_hash=existing.content_hash,
                    ),
                    content_hash=existing.content_hash,
                    created_at=existing.created_at,
                    updated_at=observed,
                    chunks=existing.chunks,
                )
                self._records[existing.knowledge_id] = refreshed
                return KnowledgeIngestionResult(True, None, (refreshed,), existing.knowledge_id)

        # Near duplicate prevention (same subject + nearly same claim in same scope).
        for existing in self._records.values():
            if (
                existing.scope == scope
                and existing.subject == normalized_subject
                and existing.status == KnowledgeStatus.ACTIVE
                and _near_duplicate(existing.normalized_content, normalized_content)
            ):
                return KnowledgeIngestionResult(True, None, (), existing.knowledge_id)

        record_id = uuid.uuid4()
        now = _utcnow()

        if correction:
            for existing in tuple(self._records.values()):
                if existing.scope == scope and existing.subject == normalized_subject and existing.status == KnowledgeStatus.ACTIVE:
                    self._records[existing.knowledge_id] = KnowledgeRecord(
                        knowledge_id=existing.knowledge_id,
                        scope=existing.scope,
                        source_type=existing.source_type,
                        source_id=existing.source_id,
                        subject=existing.subject,
                        content=existing.content,
                        normalized_content=existing.normalized_content,
                        source_title=existing.source_title,
                        source_timestamp=existing.source_timestamp,
                        observed_at=existing.observed_at,
                        effective_from=existing.effective_from,
                        effective_to=now,
                        confidence=existing.confidence,
                        freshness=existing.freshness,
                        authority=existing.authority,
                        sensitivity=existing.sensitivity,
                        status=KnowledgeStatus.SUPERSEDED,
                        provenance=existing.provenance,
                        content_hash=existing.content_hash,
                        created_at=existing.created_at,
                        updated_at=now,
                        chunks=existing.chunks,
                    )

        chunk_pairs = _split_chunks(bounded_content, self._max_chunk_chars, self._overlap_chars)
        chunks: list[KnowledgeChunk] = []
        for chunk_content, index in chunk_pairs[: self._max_chunks]:
            chunk_normalized = _normalize_text(chunk_content)
            chunk_hash = hashlib.sha256((content_hash + "|" + str(index) + "|" + chunk_normalized).encode("utf-8")).hexdigest()
            chunk_id = hashlib.sha1((content_hash + "|" + str(index)).encode("utf-8")).hexdigest()
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    order_index=index,
                    content=chunk_content,
                    normalized_content=chunk_normalized,
                    content_hash=chunk_hash,
                )
            )

        record = KnowledgeRecord(
            knowledge_id=record_id,
            scope=scope,
            source_type=source_type,
            source_id=canonical_source_id,
            subject=normalized_subject,
            content=bounded_content,
            normalized_content=normalized_content,
            source_title=source_title,
            source_timestamp=source_timestamp,
            observed_at=observed,
            effective_from=effective_from,
            effective_to=effective_to,
            confidence=max(0.0, min(1.0, float(confidence))),
            freshness=_freshness_from_timestamps(source_type, source_timestamp, observed),
            authority=authority,
            sensitivity=sensitivity,
            status=KnowledgeStatus.ACTIVE,
            provenance=KnowledgeProvenance(
                source_type=source_type,
                source_id=canonical_source_id,
                source_title=source_title,
                source_timestamp=source_timestamp,
                authority=authority,
                retrieved_at=observed,
                content_hash=content_hash,
            ),
            content_hash=content_hash,
            created_at=now,
            updated_at=now,
            chunks=tuple(chunks),
        )
        self._records[record_id] = record
        return KnowledgeIngestionResult(True, None, (record,), None)

    def ingest_structured_record(
        self,
        *,
        scope: KnowledgeScope,
        source_type: KnowledgeSourceType,
        source_id: str,
        subject: str,
        record: dict[str, Any],
        source_title: str | None = None,
        source_timestamp: datetime | None = None,
        authority: AuthorityLevel = AuthorityLevel.TRUSTED,
        confidence: float = 0.75,
    ) -> KnowledgeIngestionResult:
        flat_pairs = []
        for key in sorted(record.keys()):
            value = record[key]
            if isinstance(value, (dict, list, tuple)):
                value_text = str(value)
            else:
                value_text = str(value)
            flat_pairs.append(f"{key}={value_text}")
        content = "; ".join(flat_pairs)
        return self.ingest_text(
            scope=scope,
            source_type=source_type,
            source_id=source_id,
            subject=subject,
            content=content,
            source_title=source_title,
            source_timestamp=source_timestamp,
            authority=authority,
            confidence=confidence,
        )

    def ingest_memory_record(
        self,
        *,
        scope: KnowledgeScope,
        source_id: str,
        subject: str,
        content: str,
        source_title: str | None = None,
        confidence: float = 0.68,
    ) -> KnowledgeIngestionResult:
        return self.ingest_text(
            scope=scope,
            source_type=KnowledgeSourceType.MEMORY,
            source_id=source_id,
            subject=subject,
            content=content,
            source_title=source_title,
            authority=AuthorityLevel.USER_PROVIDED,
            confidence=confidence,
        )

    def ingest_tool_output(
        self,
        *,
        scope: KnowledgeScope,
        tool_name: str,
        source_id: str,
        subject: str,
        output: dict[str, Any],
        source_timestamp: datetime | None = None,
        confidence: float = 0.8,
    ) -> KnowledgeIngestionResult:
        flattened = "; ".join(f"{key}={output[key]}" for key in sorted(output.keys()))
        return self.ingest_text(
            scope=scope,
            source_type=KnowledgeSourceType.TOOL,
            source_id=source_id,
            subject=subject,
            content=flattened,
            source_title=tool_name,
            source_timestamp=source_timestamp,
            authority=AuthorityLevel.AUTHORITATIVE,
            confidence=confidence,
        )

    def retrieve(
        self,
        *,
        query_text: str,
        scope: KnowledgeScope,
        max_results: int | None = None,
        max_context_chars: int | None = None,
        max_sources: int | None = None,
        require_authoritative: bool = False,
        requires_external_research: bool = False,
        dependency_unavailable: bool = False,
    ) -> KnowledgeRetrievalResult:
        query = _normalize_text(query_text)
        query_tokens = _tokenize(query)
        if not query_tokens:
            return KnowledgeRetrievalResult(
                records=(),
                citations=(),
                conflicts=(),
                knowledge_boundary=KnowledgeBoundary.INSUFFICIENT_EVIDENCE,
                grounding_status=GroundingStatus.INSUFFICIENT_EVIDENCE,
                candidates_considered=0,
                context_chars=0,
                truncated_by_limit=False,
                truncated_by_budget=False,
                source_count=0,
                authoritative_source_count=0,
                stale_source_count=0,
            )

        result_limit = max(1, min(max_results or self._max_retrieval_results, self._max_retrieval_results))
        context_budget = max(200, min(max_context_chars or self._max_context_chars, self._max_context_chars))
        source_limit = max(1, min(max_sources or self._max_sources, self._max_sources))

        candidates: list[tuple[KnowledgeRecord, float]] = []
        now = _utcnow()

        for record in self._records.values():
            if not self._scope_visible(scope, record.scope):
                continue
            if record.sensitivity == KnowledgeSensitivity.SECRET:
                continue
            if _contains_secret_like_content(record.content):
                continue

            score = self._ranking_score(query_tokens, record, scope, now)
            if score <= 0:
                continue
            if require_authoritative and not _source_is_authoritative(record.authority):
                continue
            candidates.append((record, score))

        candidates.sort(
            key=lambda item: (
                -item[1],
                -item[0].confidence,
                -_AUTHORITY_WEIGHTS.get(item[0].authority, 0.0),
                -item[0].updated_at.timestamp(),
                str(item[0].knowledge_id),
            )
        )

        selected: list[KnowledgeRecord] = []
        seen_sources: set[str] = set()
        context_chars = 0
        truncated_by_limit = len(candidates) > result_limit
        truncated_by_budget = False

        for record, _score in candidates:
            if len(selected) >= result_limit:
                break
            source_key = f"{record.source_type.value}:{record.source_id}"
            if source_key not in seen_sources and len(seen_sources) >= source_limit:
                continue

            snippet = f"{record.subject}: {record.content}"
            length = len(snippet)
            if selected and context_chars + length > context_budget:
                truncated_by_budget = True
                continue
            if not selected and length > context_budget:
                selected.append(record)
                seen_sources.add(source_key)
                context_chars = length
                truncated_by_budget = True
                break

            selected.append(record)
            seen_sources.add(source_key)
            context_chars += length

        conflicts = self._detect_conflicts(selected)
        citations = tuple(
            KnowledgeCitation(
                citation_id=f"K{index}",
                knowledge_id=record.knowledge_id,
                source_type=record.source_type,
                source_id=record.source_id,
                title=record.source_title,
                source_timestamp=record.source_timestamp,
            )
            for index, record in enumerate(selected, start=1)
        )

        knowledge_boundary = self._knowledge_boundary(
            selected,
            conflicts,
            requires_external_research=requires_external_research,
            dependency_unavailable=dependency_unavailable,
        )

        grounding = self._grounding_status(selected, conflicts)

        stale_count = sum(1 for row in selected if row.freshness == KnowledgeFreshness.STALE or row.status == KnowledgeStatus.STALE)
        authoritative_count = sum(1 for row in selected if _source_is_authoritative(row.authority))

        return KnowledgeRetrievalResult(
            records=tuple(selected),
            citations=citations,
            conflicts=conflicts,
            knowledge_boundary=knowledge_boundary,
            grounding_status=grounding,
            candidates_considered=len(candidates),
            context_chars=context_chars,
            truncated_by_limit=truncated_by_limit,
            truncated_by_budget=truncated_by_budget,
            source_count=len({f"{row.source_type.value}:{row.source_id}" for row in selected}),
            authoritative_source_count=authoritative_count,
            stale_source_count=stale_count,
        )

    def _scope_visible(self, query_scope: KnowledgeScope, record_scope: KnowledgeScope) -> bool:
        if query_scope.user_id != record_scope.user_id:
            return False
        if query_scope.workspace_id != record_scope.workspace_id and not record_scope.allow_public:
            return False
        if (query_scope.business_id or "") != (record_scope.business_id or "") and not record_scope.allow_public:
            return False
        if record_scope.allow_public and not query_scope.allow_public:
            return False
        return True

    def _ranking_score(self, query_tokens: tuple[str, ...], record: KnowledgeRecord, target_scope: KnowledgeScope, now: datetime) -> float:
        searchable_text = f"{record.subject} {record.content}"
        content_tokens = set(_tokenize(searchable_text))
        if not content_tokens:
            return 0.0

        exact_phrase_bonus = 0.6 if _normalize_text(" ".join(query_tokens)) in record.normalized_content else 0.0
        query_set = set(query_tokens)
        overlap = len(query_set.intersection(content_tokens))
        if overlap <= 0:
            return 0.0
        lexical = overlap / max(1, len(query_set))

        subject_tokens = set(_tokenize(record.subject))
        subject_overlap = len(query_set.intersection(subject_tokens))
        subject_bonus = 0.2 if subject_overlap > 0 else 0.0

        recency_days = max(0.0, (now - record.observed_at).total_seconds() / 86400.0)
        recency_score = max(0.0, 0.25 - min(0.25, recency_days / 365.0))

        freshness_penalty = {
            KnowledgeFreshness.CURRENT: 0.0,
            KnowledgeFreshness.AGING: -0.05,
            KnowledgeFreshness.STALE: -0.18,
            KnowledgeFreshness.UNKNOWN: -0.07,
        }.get(record.freshness, -0.07)

        contradiction_penalty = -0.2 if record.status == KnowledgeStatus.CONFLICTED else 0.0
        stale_status_penalty = _STATUS_WEIGHTS.get(record.status, -0.4)
        authority_bonus = _AUTHORITY_WEIGHTS.get(record.authority, 0.0) * 0.35
        confidence_bonus = max(0.0, min(1.0, record.confidence)) * 0.25
        scope_bonus = _scope_specificity(target_scope, record.scope)

        return round(
            lexical
            + exact_phrase_bonus
            + subject_bonus
            + recency_score
            + authority_bonus
            + confidence_bonus
            + scope_bonus
            + freshness_penalty
            + contradiction_penalty
            + stale_status_penalty,
            6,
        )

    def _detect_conflicts(self, rows: list[KnowledgeRecord]) -> tuple[KnowledgeConflict, ...]:
        by_subject: dict[str, list[KnowledgeRecord]] = {}
        for row in rows:
            if row.status != KnowledgeStatus.ACTIVE:
                continue
            by_subject.setdefault(row.subject, []).append(row)

        conflicts: list[KnowledgeConflict] = []
        for subject, subject_rows in by_subject.items():
            hashes = {row.normalized_content for row in subject_rows}
            if len(hashes) <= 1:
                continue
            conflicts.append(
                KnowledgeConflict(
                    subject=subject,
                    knowledge_ids=tuple(sorted((row.knowledge_id for row in subject_rows), key=str)),
                )
            )
        return tuple(conflicts)

    def _knowledge_boundary(
        self,
        rows: list[KnowledgeRecord],
        conflicts: tuple[KnowledgeConflict, ...],
        *,
        requires_external_research: bool,
        dependency_unavailable: bool,
    ) -> KnowledgeBoundary:
        if dependency_unavailable:
            return KnowledgeBoundary.DEPENDENCY_UNAVAILABLE
        if conflicts:
            return KnowledgeBoundary.CONFLICTING_KNOWLEDGE
        if rows:
            return KnowledgeBoundary.KNOWLEDGE_AVAILABLE
        if requires_external_research:
            return KnowledgeBoundary.RESEARCH_REQUIRED
        return KnowledgeBoundary.DATA_REQUIRED

    def _grounding_status(
        self,
        rows: list[KnowledgeRecord],
        conflicts: tuple[KnowledgeConflict, ...],
    ) -> GroundingStatus:
        if conflicts:
            return GroundingStatus.CONFLICTED
        if not rows:
            return GroundingStatus.INSUFFICIENT_EVIDENCE
        authoritative = [row for row in rows if _source_is_authoritative(row.authority)]
        if authoritative:
            return GroundingStatus.GROUNDED
        if rows:
            return GroundingStatus.PARTIALLY_GROUNDED
        return GroundingStatus.UNGROUNDED
