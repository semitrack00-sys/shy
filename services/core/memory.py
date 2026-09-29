import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:
    psycopg = None
    dict_row = None

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://shy:shy_local_dev@host.docker.internal:5432/shy"
)

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class MemoryRecord:
    message_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    model: str | None = None
    provider: str | None = None
    task_type: str | None = None


@dataclass(frozen=True)
class MemoryQuery:
    query_text: str
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    include_cross_conversation: bool = False
    max_results: int = 8
    max_context_chars: int = 2400
    max_candidates: int = 80


@dataclass(frozen=True)
class MemorySelection:
    selected_records: tuple[MemoryRecord, ...]
    selected_messages: tuple[dict[str, str], ...]
    query_valid: bool
    failure_reason: str | None
    candidates_considered: int
    context_chars: int
    truncated_by_limit: bool
    truncated_by_budget: bool


def connect():
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg unavailable")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def ensure_default_user():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, display_name)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (DEFAULT_USER_ID, "Local SHY User"),
            )


def create_conversation() -> uuid.UUID:
    conversation_id = uuid.uuid4()

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (id, user_id)
                VALUES (%s, %s)
                """,
                (conversation_id, DEFAULT_USER_ID),
            )

    return conversation_id


def conversation_exists(conversation_id: uuid.UUID) -> bool:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM conversations
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, DEFAULT_USER_ID),
            )
            return cur.fetchone() is not None


def load_messages(conversation_id: uuid.UUID, limit: int = 20):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content
                FROM (
                    SELECT id, role, content, created_at
                    FROM messages
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                ) recent
                ORDER BY created_at ASC, id ASC
                """,
                (conversation_id, limit),
            )
            return cur.fetchall()


def build_memory_query(
    query_text: str,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID = DEFAULT_USER_ID,
    include_cross_conversation: bool = False,
    max_results: int = 8,
    max_context_chars: int = 2400,
    max_candidates: int = 80,
) -> MemoryQuery:
    return MemoryQuery(
        query_text=str(query_text or "").strip(),
        user_id=user_id,
        conversation_id=conversation_id,
        include_cross_conversation=bool(include_cross_conversation),
        max_results=max_results,
        max_context_chars=max_context_chars,
        max_candidates=max_candidates,
    )


def retrieve_memory_context(
    query: MemoryQuery,
    records_loader: Callable[[MemoryQuery], list[MemoryRecord]] | None = None,
) -> MemorySelection:
    try:
        loader = records_loader or load_memory_records
        records = loader(query)
    except Exception:
        return MemorySelection(
            selected_records=(),
            selected_messages=(),
            query_valid=True,
            failure_reason="MEMORY_RETRIEVAL_FAILED",
            candidates_considered=0,
            context_chars=0,
            truncated_by_limit=False,
            truncated_by_budget=False,
        )

    return select_memory_context(query, records)


def select_memory_context(query: MemoryQuery, records: list[MemoryRecord]) -> MemorySelection:
    if not _valid_query(query):
        return MemorySelection(
            selected_records=(),
            selected_messages=(),
            query_valid=False,
            failure_reason="INVALID_QUERY",
            candidates_considered=0,
            context_chars=0,
            truncated_by_limit=False,
            truncated_by_budget=False,
        )

    user_scoped = [record for record in records if record.user_id == query.user_id]
    if not query.include_cross_conversation:
        user_scoped = [record for record in user_scoped if record.conversation_id == query.conversation_id]

    if not user_scoped:
        return MemorySelection(
            selected_records=(),
            selected_messages=(),
            query_valid=True,
            failure_reason=None,
            candidates_considered=0,
            context_chars=0,
            truncated_by_limit=False,
            truncated_by_budget=False,
        )

    query_tokens = _tokenize(query.query_text)
    if not query_tokens:
        return MemorySelection(
            selected_records=(),
            selected_messages=(),
            query_valid=False,
            failure_reason="INVALID_QUERY",
            candidates_considered=0,
            context_chars=0,
            truncated_by_limit=False,
            truncated_by_budget=False,
        )

    scored = []
    recency_weights = _recency_weights(user_scoped)

    for record in user_scoped:
        lexical_score = _lexical_score(query_tokens, record.content)
        if lexical_score <= 0.0:
            continue
        recency_weight = recency_weights.get(record.message_id, 0.0)
        combined = lexical_score + recency_weight
        scored.append((record, lexical_score, recency_weight, combined))

    if not scored:
        return MemorySelection(
            selected_records=(),
            selected_messages=(),
            query_valid=True,
            failure_reason=None,
            candidates_considered=0,
            context_chars=0,
            truncated_by_limit=False,
            truncated_by_budget=False,
        )

    # Conservative deduplication: exact normalized text only.
    deduped: dict[str, tuple[MemoryRecord, float, float, float]] = {}
    for row in scored:
        record = row[0]
        key = _normalize_text(record.content)
        existing = deduped.get(key)
        if existing is None or _ranking_key(row) < _ranking_key(existing):
            deduped[key] = row

    ranked = sorted(deduped.values(), key=_ranking_key)
    candidates_considered = len(ranked)

    truncated_by_limit = len(ranked) > query.max_results
    top_ranked = ranked[: query.max_results]

    selected_records: list[MemoryRecord] = []
    used_chars = 0
    truncated_by_budget = False

    for record, _, _, _ in top_ranked:
        message_len = len(record.content)
        if selected_records and used_chars + message_len > query.max_context_chars:
            truncated_by_budget = True
            continue
        if not selected_records and message_len > query.max_context_chars:
            selected_records.append(record)
            used_chars = message_len
            truncated_by_budget = True
            continue

        selected_records.append(record)
        used_chars += message_len

    # Chronological order for downstream model context.
    ordered_for_context = sorted(selected_records, key=lambda item: (item.created_at, str(item.message_id)))
    selected_messages = tuple({"role": item.role, "content": item.content} for item in ordered_for_context)

    return MemorySelection(
        selected_records=tuple(selected_records),
        selected_messages=selected_messages,
        query_valid=True,
        failure_reason=None,
        candidates_considered=candidates_considered,
        context_chars=used_chars,
        truncated_by_limit=truncated_by_limit,
        truncated_by_budget=truncated_by_budget,
    )


def load_memory_records(query: MemoryQuery) -> list[MemoryRecord]:
    with connect() as conn:
        with conn.cursor() as cur:
            if query.include_cross_conversation:
                cur.execute(
                    """
                    SELECT
                        m.id,
                        c.user_id,
                        m.conversation_id,
                        m.role,
                        m.content,
                        m.created_at,
                        m.model,
                        m.provider,
                        m.task_type
                    FROM messages m
                    INNER JOIN conversations c ON c.id = m.conversation_id
                    WHERE c.user_id = %s
                    ORDER BY m.created_at DESC, m.id DESC
                    LIMIT %s
                    """,
                    (query.user_id, query.max_candidates),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        m.id,
                        c.user_id,
                        m.conversation_id,
                        m.role,
                        m.content,
                        m.created_at,
                        m.model,
                        m.provider,
                        m.task_type
                    FROM messages m
                    INNER JOIN conversations c ON c.id = m.conversation_id
                    WHERE c.user_id = %s AND m.conversation_id = %s
                    ORDER BY m.created_at DESC, m.id DESC
                    LIMIT %s
                    """,
                    (query.user_id, query.conversation_id, query.max_candidates),
                )

            rows = cur.fetchall()

    records: list[MemoryRecord] = []
    for row in rows:
        created_at = row["created_at"]
        if not isinstance(created_at, datetime):
            created_at = datetime.fromisoformat(str(created_at))
        records.append(
            MemoryRecord(
                message_id=row["id"],
                user_id=row["user_id"],
                conversation_id=row["conversation_id"],
                role=str(row["role"]),
                content=str(row["content"]),
                created_at=created_at,
                model=row.get("model"),
                provider=row.get("provider"),
                task_type=row.get("task_type"),
            )
        )
    return records


def _valid_query(query: MemoryQuery) -> bool:
    if not query.query_text.strip():
        return False
    if query.max_results < 1 or query.max_results > 25:
        return False
    if query.max_context_chars < 1 or query.max_context_chars > 64000:
        return False
    if query.max_candidates < query.max_results or query.max_candidates > 500:
        return False
    return True


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _tokenize(value: str) -> tuple[str, ...]:
    tokens = re.findall(r"[a-z0-9_]+", _normalize_text(value))
    filtered = [token for token in tokens if len(token) >= 2]
    return tuple(filtered)


def _lexical_score(query_tokens: tuple[str, ...], content: str) -> float:
    content_tokens = _tokenize(content)
    if not content_tokens:
        return 0.0

    content_set = set(content_tokens)
    matches = [token for token in query_tokens if token in content_set]
    if not matches:
        return 0.0

    # Primary lexical overlap, then slight deterministic boost for longer terms.
    base = len(matches) / max(1, len(set(query_tokens)))
    length_bonus = sum(0.02 for token in set(matches) if len(token) >= 6)
    return round(base + min(0.12, length_bonus), 4)


def _recency_weights(records: list[MemoryRecord]) -> dict[uuid.UUID, float]:
    ranked = sorted(records, key=lambda row: (row.created_at, str(row.message_id)), reverse=True)
    total = len(ranked)
    if total == 1:
        return {ranked[0].message_id: 0.25}

    weights: dict[uuid.UUID, float] = {}
    for index, record in enumerate(ranked):
        bounded = (total - index - 1) / max(1, total - 1)
        weights[record.message_id] = round(0.25 * bounded, 4)
    return weights


def _ranking_key(row: tuple[MemoryRecord, float, float, float]):
    record, lexical_score, recency_weight, combined = row
    return (
        -combined,
        -lexical_score,
        -recency_weight,
        -record.created_at.timestamp(),
        str(record.message_id),
    )


def save_message(
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    model: str | None = None,
    provider: str | None = None,
    task_type: str | None = None,
):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (
                    id,
                    conversation_id,
                    role,
                    content,
                    model,
                    provider,
                    task_type
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid.uuid4(),
                    conversation_id,
                    role,
                    content,
                    model,
                    provider,
                    task_type,
                ),
            )

            cur.execute(
                """
                UPDATE conversations
                SET updated_at = NOW()
                WHERE id = %s
                """,
                (conversation_id,),
            )
