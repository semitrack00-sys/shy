import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:
    psycopg = None
    dict_row = None

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://shy:shy_local_dev@127.0.0.1:5432/shy"
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


class MemoryCategory(str, Enum):
    SESSION = "SESSION"
    USER_FACT = "USER_FACT"
    PREFERENCE = "PREFERENCE"
    PROJECT = "PROJECT"
    TASK_OUTCOME = "TASK_OUTCOME"
    CORRECTION = "CORRECTION"


class MemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class DurableMemoryRecord:
    memory_id: uuid.UUID
    user_id: uuid.UUID
    category: MemoryCategory
    subject_key: str
    content: str
    normalized_content: str
    confidence: float
    source_conversation_id: uuid.UUID | None
    source_task_id: str | None
    status: MemoryStatus
    superseded_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None
    use_count: int


@dataclass(frozen=True)
class DurableMemoryCandidate:
    category: MemoryCategory
    subject_key: str
    content: str
    confidence: float
    is_correction: bool = False


@dataclass(frozen=True)
class DurableMemorySelection:
    selected_records: tuple[DurableMemoryRecord, ...]
    selected_messages: tuple[dict[str, str], ...]
    candidates_considered: int
    context_chars: int
    truncated_by_limit: bool
    truncated_by_budget: bool


SECRET_MARKERS = (
    "password",
    "passwd",
    "api key",
    "api_key",
    "access token",
    "oauth",
    "approval token",
    "database_url",
    "bearer",
    "secret",
    "private key",
    "chain-of-thought",
    "hidden reasoning",
    "verifier reasoning",
    "environment variable",
    "env dump",
    "task plan",
    "step_id",
    "action_type",
    "tool trace",
)


NON_DURABLE_PATTERNS = (
    r"^\s*(hi|hello|hey|thanks|thank you|good morning|good night)[!.\s]*$",
    r"^\s*what\s+is\s+[0-9\s%+\-*/().of]+\??\s*$",
    r"^\s*calculate\b",
)


def local_memory_user(project_id: str | None = None) -> uuid.UUID:
    if project_id is None:
        return DEFAULT_USER_ID
    if not isinstance(project_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", project_id):
        raise ValueError("invalid_project_id")
    return uuid.uuid5(DEFAULT_USER_ID, "project:" + project_id)


def ensure_memory_schema():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute("""CREATE TABLE IF NOT EXISTS memory_save_preferences (
                user_id UUID PRIMARY KEY,
                automatic_saving BOOLEAN NOT NULL,
                revision BIGINT NOT NULL DEFAULT 1,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )""")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id UUID PRIMARY KEY,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id UUID PRIMARY KEY,
                    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    model TEXT,
                    provider TEXT,
                    task_type TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS durable_memories (
                    memory_id UUID PRIMARY KEY,
                    user_id UUID NOT NULL,
                    category TEXT NOT NULL,
                    subject_key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    normalized_content TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source_conversation_id UUID,
                    source_task_id TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    superseded_by UUID,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_used_at TIMESTAMPTZ,
                    use_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_user_id
                ON conversations (user_id, updated_at DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
                ON messages (conversation_id, created_at DESC, id DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_durable_memories_user_status
                ON durable_memories (user_id, status, updated_at DESC)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_durable_memories_user_subject
                ON durable_memories (user_id, subject_key)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_durable_memories_user_category
                ON durable_memories (user_id, category, updated_at DESC)
                """
            )
            cur.execute("""UPDATE durable_memories SET user_id = %s
                WHERE user_id = %s AND (source_conversation_id IS NULL OR EXISTS
                (SELECT 1 FROM conversations c WHERE c.id = durable_memories.source_conversation_id AND c.user_id = %s))""",
                (DEFAULT_USER_ID, uuid.uuid5(uuid.NAMESPACE_DNS, "default||anonymous"), DEFAULT_USER_ID))


def connect():
    if psycopg is None or dict_row is None:
        raise RuntimeError("psycopg unavailable")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def _durable_memory_failure_enabled() -> bool:
    return os.getenv("SHY_FORCE_DURABLE_MEMORY_FAILURE", "0").strip() == "1"


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


def create_conversation(user_id: uuid.UUID = DEFAULT_USER_ID) -> uuid.UUID:
    conversation_id = uuid.uuid4()

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (id, display_name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                        (user_id, "Local SHY memory scope"))
            cur.execute(
                """
                INSERT INTO conversations (id, user_id)
                VALUES (%s, %s)
                """,
                (conversation_id, user_id),
            )

    return conversation_id


def conversation_exists(conversation_id: uuid.UUID, user_id: uuid.UUID = DEFAULT_USER_ID) -> bool:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM conversations
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )
            return cur.fetchone() is not None


def load_messages(conversation_id: uuid.UUID, limit: int = 20, user_id: uuid.UUID = DEFAULT_USER_ID):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content
                FROM (
                    SELECT id, role, content, created_at
                    FROM messages
                    WHERE conversation_id = %s AND EXISTS (SELECT 1 FROM conversations c WHERE c.id = messages.conversation_id AND c.user_id = %s)
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                ) recent
                ORDER BY created_at ASC, id ASC
                """,
                (conversation_id, user_id, limit),
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


def _normalize_subject_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_.-]+", ".", str(value or "").strip().lower())
    normalized = normalized.strip(".")
    if not normalized:
        normalized = "general"
    return normalized[:120]


def _normalize_memory_content(value: str, max_chars: int = 500) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text


def _contains_secret_like_content(value: str) -> bool:
    lowered = str(value or "").lower()
    if "sk-" in lowered:
        return True
    if re.search(r"\b[a-z0-9_\-]*token\b\s*[:=]", lowered):
        return True
    return any(marker in lowered for marker in SECRET_MARKERS)


def _is_non_durable_message(value: str) -> bool:
    text = " ".join(str(value or "").split())
    if len(text) < 8:
        return True
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in NON_DURABLE_PATTERNS)


def _extract_subject_and_category(text: str) -> tuple[MemoryCategory, str, float] | None:
    lowered = text.lower()

    if "not" in lowered and any(token in lowered for token in ("now", "actually", "instead")):
        if "company" in lowered:
            return (MemoryCategory.CORRECTION, "user.company", 0.92)
        if "language" in lowered:
            return (MemoryCategory.CORRECTION, "preference.language", 0.9)
        if "project" in lowered or "repo" in lowered:
            return (MemoryCategory.CORRECTION, "project.configuration", 0.88)
        return (MemoryCategory.CORRECTION, "correction.general", 0.9)

    if "for this session" in lowered or "this session" in lowered:
        return (MemoryCategory.SESSION, "session.context", 0.55)

    if any(token in lowered for token in ("prefer", "i like", "my preference", "i want")):
        if "language" in lowered:
            return (MemoryCategory.PREFERENCE, "preference.language", 0.86)
        if "theme" in lowered or "dark mode" in lowered or "light mode" in lowered:
            return (MemoryCategory.PREFERENCE, "preference.theme", 0.84)
        if "editor" in lowered or "format" in lowered:
            return (MemoryCategory.PREFERENCE, "preference.workflow", 0.8)
        return (MemoryCategory.PREFERENCE, "preference.general", 0.72)

    if any(token in lowered for token in ("my name is", "i am ", "my company is", "i work at", "our company name is", "company name is")):
        if (
            "my company is" in lowered
            or "i work at" in lowered
            or "our company name is" in lowered
            or "company name is" in lowered
        ):
            return (MemoryCategory.USER_FACT, "user.company", 0.86)
        if "my name is" in lowered:
            return (MemoryCategory.USER_FACT, "user.name", 0.9)
        return (MemoryCategory.USER_FACT, "user.profile", 0.74)

    if any(token in lowered for token in ("project", "repository", "repo", "codebase", "infrastructure")):
        project_match = re.search(r"\b([a-z0-9_-]+)\s+project\b", lowered)
        if not project_match:
            project_match = re.search(r"\bproject\s+([a-z0-9_-]+)\b", lowered)
        project_subject = f"project.{project_match.group(1)}.configuration" if project_match else "project.configuration"
        if any(token in lowered for token in ("uses", "is configured", "runs on", "default branch", "port")):
            return (MemoryCategory.PROJECT, project_subject, 0.82)
        return (MemoryCategory.PROJECT, project_subject.replace("configuration", "context"), 0.7)

    if any(token in lowered for token in ("we decided", "final decision", "task outcome", "resolved by", "final result")):
        return (MemoryCategory.TASK_OUTCOME, "task.outcome", 0.78)

    return None


def classify_memory_candidate(message: str) -> DurableMemoryCandidate | None:
    text = _normalize_memory_content(message)
    if not text:
        return None

    if _contains_secret_like_content(text):
        return None

    if _is_non_durable_message(text):
        return None

    extracted = _extract_subject_and_category(text)
    if extracted is None:
        return None

    category, subject_key, confidence = extracted
    is_correction = category == MemoryCategory.CORRECTION or bool(re.search(r"\b(not|instead|actually now)\b", text, flags=re.IGNORECASE))

    if category == MemoryCategory.PREFERENCE and subject_key == "preference.theme":
        lowered = text.lower()
        if "dark mode" in lowered:
            text = "I prefer dark mode."
        elif "light mode" in lowered:
            text = "I prefer light mode."

    if is_correction:
        if subject_key == "user.company":
            match = re.search(r"my\s+company\s+is\s+now\s+(?:called\s+)?([^,.]+)", text, flags=re.IGNORECASE)
            if not match:
                match = re.search(r"my\s+company\s+is\s+(?:called\s+)?([^,.]+),\s*not\s+([^,.]+)", text, flags=re.IGNORECASE)
            if match:
                corrected = match.group(1).strip()
                text = f"My company is {corrected}."
        elif subject_key == "preference.language":
            match = re.search(r"(?:prefer|use)\s+([a-zA-Z0-9_\-+ ]+)", text, flags=re.IGNORECASE)
            if match:
                corrected = match.group(1).strip()
                text = f"I prefer {corrected}."
        elif subject_key.startswith("project"):
            match = re.search(r"(?:project|repo)[^,.]*\s+now\s+([^,.]+)", text, flags=re.IGNORECASE)
            if match:
                corrected = match.group(1).strip()
                text = f"Project configuration is now {corrected}."

        text = _normalize_memory_content(text)

    return DurableMemoryCandidate(
        category=category,
        subject_key=_normalize_subject_key(subject_key),
        content=text,
        confidence=max(0.0, min(1.0, confidence)),
        is_correction=is_correction,
    )


def _coerce_durable_row(row: dict) -> DurableMemoryRecord:
    created_at = row["created_at"]
    updated_at = row["updated_at"]
    last_used_at = row.get("last_used_at")

    if not isinstance(created_at, datetime):
        created_at = datetime.fromisoformat(str(created_at))
    if not isinstance(updated_at, datetime):
        updated_at = datetime.fromisoformat(str(updated_at))
    if last_used_at is not None and not isinstance(last_used_at, datetime):
        last_used_at = datetime.fromisoformat(str(last_used_at))

    source_conversation_id = row.get("source_conversation_id")
    if source_conversation_id is not None and not isinstance(source_conversation_id, uuid.UUID):
        source_conversation_id = uuid.UUID(str(source_conversation_id))

    superseded_by = row.get("superseded_by")
    if superseded_by is not None and not isinstance(superseded_by, uuid.UUID):
        superseded_by = uuid.UUID(str(superseded_by))

    return DurableMemoryRecord(
        memory_id=row["memory_id"],
        user_id=row["user_id"],
        category=MemoryCategory(str(row["category"])),
        subject_key=str(row["subject_key"]),
        content=str(row["content"]),
        normalized_content=str(row["normalized_content"]),
        confidence=float(row["confidence"]),
        source_conversation_id=source_conversation_id,
        source_task_id=row.get("source_task_id"),
        status=MemoryStatus(str(row["status"])),
        superseded_by=superseded_by,
        created_at=created_at,
        updated_at=updated_at,
        last_used_at=last_used_at,
        use_count=int(row.get("use_count", 0)),
    )


def _load_active_memories_for_subject(user_id: uuid.UUID, subject_key: str) -> list[DurableMemoryRecord]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_id,
                    user_id,
                    category,
                    subject_key,
                    content,
                    normalized_content,
                    confidence,
                    source_conversation_id,
                    source_task_id,
                    status,
                    superseded_by,
                    created_at,
                    updated_at,
                    last_used_at,
                    use_count
                FROM durable_memories
                WHERE user_id = %s
                  AND subject_key = %s
                  AND status = %s
                ORDER BY updated_at DESC, memory_id DESC
                """,
                (user_id, subject_key, MemoryStatus.ACTIVE.value),
            )
            rows = cur.fetchall()
    return [_coerce_durable_row(row) for row in rows]


def memory_preference_lock(cur, user_id):
    # Shared by all automatic promotions and preference writes. An acknowledged
    # pause waits for earlier promotions to finish and prevents later writes.
    cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                ("memory-save-preference:" + str(user_id),))


def read_memory_save_preference(cur, user_id):
    cur.execute("SELECT automatic_saving, revision FROM memory_save_preferences WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    # Preserve existing installations' behavior until the user reviews it.
    return {"automatic_saving": row["automatic_saving"] if row else True,
            "revision": str(row["revision"]) if row else "0",
            "reviewed": row is not None}


def promote_memory_candidate(candidate, conversation_id, user_id=DEFAULT_USER_ID, source_task_id=None):
    with connect() as conn:
        with conn.cursor() as cur:
            memory_preference_lock(cur, user_id)
            if not read_memory_save_preference(cur, user_id)["automatic_saving"]:
                return None
            return _promote_memory_candidate_unchecked(candidate, conversation_id, user_id, source_task_id)


def _promote_memory_candidate_unchecked(
    candidate: DurableMemoryCandidate,
    conversation_id: uuid.UUID | None,
    user_id: uuid.UUID = DEFAULT_USER_ID,
    source_task_id: str | None = None,
) -> DurableMemoryRecord | None:
    if _durable_memory_failure_enabled():
        raise RuntimeError("Durable memory promotion unavailable")

    if _contains_secret_like_content(candidate.content):
        return None

    normalized_content = _normalize_text(candidate.content)
    active_existing = _load_active_memories_for_subject(user_id, candidate.subject_key)

    for existing in active_existing:
        if existing.category == candidate.category and existing.normalized_content == normalized_content:
            with connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE durable_memories
                        SET
                            updated_at = NOW(),
                            last_used_at = NOW(),
                            use_count = use_count + 1,
                            confidence = GREATEST(confidence, %s)
                        WHERE memory_id = %s
                        """,
                        (candidate.confidence, existing.memory_id),
                    )
            return existing

    new_memory_id = uuid.uuid4()

    with connect() as conn:
        with conn.cursor() as cur:
            if candidate.is_correction:
                cur.execute(
                    """
                    UPDATE durable_memories
                    SET
                        status = %s,
                        superseded_by = %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                      AND subject_key = %s
                      AND status = %s
                    """,
                    (
                        MemoryStatus.SUPERSEDED.value,
                        new_memory_id,
                        user_id,
                        candidate.subject_key,
                        MemoryStatus.ACTIVE.value,
                    ),
                )

            cur.execute(
                """
                INSERT INTO durable_memories (
                    memory_id,
                    user_id,
                    category,
                    subject_key,
                    content,
                    normalized_content,
                    confidence,
                    source_conversation_id,
                    source_task_id,
                    status,
                    created_at,
                    updated_at,
                    last_used_at,
                    use_count
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW(), %s)
                """,
                (
                    new_memory_id,
                    user_id,
                    candidate.category.value,
                    candidate.subject_key,
                    candidate.content,
                    normalized_content,
                    candidate.confidence,
                    conversation_id,
                    source_task_id,
                    MemoryStatus.ACTIVE.value,
                    1,
                ),
            )

            cur.execute(
                """
                SELECT
                    memory_id,
                    user_id,
                    category,
                    subject_key,
                    content,
                    normalized_content,
                    confidence,
                    source_conversation_id,
                    source_task_id,
                    status,
                    superseded_by,
                    created_at,
                    updated_at,
                    last_used_at,
                    use_count
                FROM durable_memories
                WHERE memory_id = %s
                """,
                (new_memory_id,),
            )
            row = cur.fetchone()

    if row is None:
        return None

    return _coerce_durable_row(row)


def try_promote_message_to_memory(
    message: str,
    conversation_id: uuid.UUID | None,
    user_id: uuid.UUID = DEFAULT_USER_ID,
    source_task_id: str | None = None,
) -> DurableMemoryRecord | None:
    candidate = classify_memory_candidate(message)
    if candidate is None:
        return None
    return promote_memory_candidate(candidate, conversation_id=conversation_id, user_id=user_id, source_task_id=source_task_id)


def _category_weight(category: MemoryCategory) -> float:
    weights = {
        MemoryCategory.USER_FACT: 0.2,
        MemoryCategory.PREFERENCE: 0.17,
        MemoryCategory.PROJECT: 0.15,
        MemoryCategory.TASK_OUTCOME: 0.13,
        MemoryCategory.CORRECTION: 0.22,
        MemoryCategory.SESSION: 0.06,
    }
    return weights.get(category, 0.0)


def _memory_ranking_score(query_tokens: tuple[str, ...], memory_record: DurableMemoryRecord, conversation_id: uuid.UUID | None) -> float:
    content_score = _lexical_score(query_tokens, f"{memory_record.subject_key} {memory_record.content}")
    subject_tokens = _tokenize(memory_record.subject_key)
    exact_entity_bonus = 0.2 if any(token in query_tokens for token in subject_tokens) else 0.0
    use_bonus = min(0.2, 0.02 * memory_record.use_count)
    category_bonus = _category_weight(memory_record.category)
    recency_bonus = 0.04 if memory_record.last_used_at is not None else 0.0
    conversation_bonus = 0.06 if conversation_id and memory_record.source_conversation_id == conversation_id else 0.0
    return round(content_score + exact_entity_bonus + use_bonus + category_bonus + recency_bonus + conversation_bonus, 4)


def retrieve_durable_memory_context(
    query_text: str,
    conversation_id: uuid.UUID | None,
    user_id: uuid.UUID = DEFAULT_USER_ID,
    max_results: int = 5,
    max_context_chars: int = 1200,
) -> DurableMemorySelection:
    if _durable_memory_failure_enabled():
        raise RuntimeError("Durable memory retrieval unavailable")

    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return DurableMemorySelection((), (), 0, 0, False, False)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    memory_id,
                    user_id,
                    category,
                    subject_key,
                    content,
                    normalized_content,
                    confidence,
                    source_conversation_id,
                    source_task_id,
                    status,
                    superseded_by,
                    created_at,
                    updated_at,
                    last_used_at,
                    use_count
                FROM durable_memories
                WHERE user_id = %s
                  AND status = %s
                ORDER BY updated_at DESC, memory_id DESC
                LIMIT %s
                """,
                (user_id, MemoryStatus.ACTIVE.value, 250),
            )
            rows = cur.fetchall()

    records = [_coerce_durable_row(row) for row in rows]
    scored: list[tuple[DurableMemoryRecord, float]] = []
    for record in records:
        score = _memory_ranking_score(query_tokens, record, conversation_id)
        if score > 0:
            scored.append((record, score))

    scored.sort(key=lambda item: (-item[1], -item[0].confidence, -item[0].updated_at.timestamp(), str(item[0].memory_id)))

    truncated_by_limit = len(scored) > max_results
    selected: list[DurableMemoryRecord] = []
    context_chars = 0
    truncated_by_budget = False

    for record, _score in scored[:max_results]:
        message = f"[{record.category.value}] {record.subject_key}: {record.content}"
        message_len = len(message)

        if selected and context_chars + message_len > max_context_chars:
            truncated_by_budget = True
            continue

        if not selected and message_len > max_context_chars:
            selected.append(record)
            context_chars = message_len
            truncated_by_budget = True
            continue

        selected.append(record)
        context_chars += message_len

    selected_ids = [record.memory_id for record in selected]
    if selected_ids:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE durable_memories
                    SET
                        last_used_at = NOW(),
                        use_count = use_count + 1,
                        updated_at = NOW()
                    WHERE memory_id = ANY(%s)
                    """,
                    (selected_ids,),
                )

    selected_messages = tuple(
        {
            "role": "assistant",
            "content": f"Memory: [{record.category.value}] {record.subject_key}: {record.content}",
        }
        for record in selected
    )

    return DurableMemorySelection(
        selected_records=tuple(selected),
        selected_messages=selected_messages,
        candidates_considered=len(scored),
        context_chars=context_chars,
        truncated_by_limit=truncated_by_limit,
        truncated_by_budget=truncated_by_budget,
    )


class InMemoryDurableMemoryStore:
    def __init__(self):
        self._records: dict[uuid.UUID, DurableMemoryRecord] = {}

    def list_records(self, user_id: uuid.UUID | None = None) -> list[DurableMemoryRecord]:
        records = list(self._records.values())
        if user_id is not None:
            records = [row for row in records if row.user_id == user_id]
        records.sort(key=lambda row: (row.updated_at, str(row.memory_id)), reverse=True)
        return records

    def export_state(self) -> tuple[DurableMemoryRecord, ...]:
        return tuple(self._records.values())

    def import_state(self, rows: tuple[DurableMemoryRecord, ...] | list[DurableMemoryRecord]) -> None:
        self._records = {row.memory_id: row for row in rows}

    def promote(
        self,
        candidate: DurableMemoryCandidate,
        conversation_id: uuid.UUID | None,
        user_id: uuid.UUID,
        source_task_id: str | None = None,
    ) -> DurableMemoryRecord | None:
        if _contains_secret_like_content(candidate.content):
            return None

        normalized_content = _normalize_text(candidate.content)
        now = datetime.utcnow()

        active = [
            row
            for row in self._records.values()
            if row.user_id == user_id
            and row.subject_key == candidate.subject_key
            and row.status == MemoryStatus.ACTIVE
        ]

        for existing in active:
            if existing.category == candidate.category and existing.normalized_content == normalized_content:
                updated = DurableMemoryRecord(
                    memory_id=existing.memory_id,
                    user_id=existing.user_id,
                    category=existing.category,
                    subject_key=existing.subject_key,
                    content=existing.content,
                    normalized_content=existing.normalized_content,
                    confidence=max(existing.confidence, candidate.confidence),
                    source_conversation_id=existing.source_conversation_id,
                    source_task_id=existing.source_task_id,
                    status=existing.status,
                    superseded_by=existing.superseded_by,
                    created_at=existing.created_at,
                    updated_at=now,
                    last_used_at=now,
                    use_count=existing.use_count + 1,
                )
                self._records[existing.memory_id] = updated
                return updated

        new_id = uuid.uuid4()

        if candidate.is_correction:
            for existing in active:
                superseded = DurableMemoryRecord(
                    memory_id=existing.memory_id,
                    user_id=existing.user_id,
                    category=existing.category,
                    subject_key=existing.subject_key,
                    content=existing.content,
                    normalized_content=existing.normalized_content,
                    confidence=existing.confidence,
                    source_conversation_id=existing.source_conversation_id,
                    source_task_id=existing.source_task_id,
                    status=MemoryStatus.SUPERSEDED,
                    superseded_by=new_id,
                    created_at=existing.created_at,
                    updated_at=now,
                    last_used_at=existing.last_used_at,
                    use_count=existing.use_count,
                )
                self._records[existing.memory_id] = superseded

        record = DurableMemoryRecord(
            memory_id=new_id,
            user_id=user_id,
            category=candidate.category,
            subject_key=candidate.subject_key,
            content=_normalize_memory_content(candidate.content),
            normalized_content=normalized_content,
            confidence=candidate.confidence,
            source_conversation_id=conversation_id,
            source_task_id=source_task_id,
            status=MemoryStatus.ACTIVE,
            superseded_by=None,
            created_at=now,
            updated_at=now,
            last_used_at=now,
            use_count=1,
        )
        self._records[new_id] = record
        return record

    def retrieve(
        self,
        query_text: str,
        conversation_id: uuid.UUID | None,
        user_id: uuid.UUID,
        max_results: int = 5,
        max_context_chars: int = 1200,
    ) -> DurableMemorySelection:
        query_tokens = _tokenize(query_text)
        if not query_tokens:
            return DurableMemorySelection((), (), 0, 0, False, False)

        records = [
            row
            for row in self._records.values()
            if row.user_id == user_id and row.status == MemoryStatus.ACTIVE
        ]

        scored: list[tuple[DurableMemoryRecord, float]] = []
        for record in records:
            score = _memory_ranking_score(query_tokens, record, conversation_id)
            if score > 0:
                scored.append((record, score))

        scored.sort(key=lambda item: (-item[1], -item[0].confidence, -item[0].updated_at.timestamp(), str(item[0].memory_id)))

        truncated_by_limit = len(scored) > max_results
        selected: list[DurableMemoryRecord] = []
        context_chars = 0
        truncated_by_budget = False

        for record, _score in scored[:max_results]:
            message = f"[{record.category.value}] {record.subject_key}: {record.content}"
            message_len = len(message)
            if selected and context_chars + message_len > max_context_chars:
                truncated_by_budget = True
                continue
            if not selected and message_len > max_context_chars:
                selected.append(record)
                context_chars = message_len
                truncated_by_budget = True
                continue
            selected.append(record)
            context_chars += message_len

        now = datetime.utcnow()
        for record in selected:
            self._records[record.memory_id] = DurableMemoryRecord(
                memory_id=record.memory_id,
                user_id=record.user_id,
                category=record.category,
                subject_key=record.subject_key,
                content=record.content,
                normalized_content=record.normalized_content,
                confidence=record.confidence,
                source_conversation_id=record.source_conversation_id,
                source_task_id=record.source_task_id,
                status=record.status,
                superseded_by=record.superseded_by,
                created_at=record.created_at,
                updated_at=now,
                last_used_at=now,
                use_count=record.use_count + 1,
            )

        selected_messages = tuple(
            {
                "role": "assistant",
                "content": f"Memory: [{record.category.value}] {record.subject_key}: {record.content}",
            }
            for record in selected
        )

        return DurableMemorySelection(
            selected_records=tuple(selected),
            selected_messages=selected_messages,
            candidates_considered=len(scored),
            context_chars=context_chars,
            truncated_by_limit=truncated_by_limit,
            truncated_by_budget=truncated_by_budget,
        )

