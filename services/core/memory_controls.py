"""Explicit controls over the existing local user's PostgreSQL durable memories."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

import memory

router = APIRouter(prefix="/memories", tags=["Saved memories"])


class MemoryBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "").rstrip("/")
        if (scope["type"] != "http" or scope.get("method") not in {"POST", "PATCH"}
                or not (path == "/memories" or path.startswith("/memories/"))):
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > 8192:
                await send({"type": "http.response.start", "status": 413,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"memory_request_too_large"}'})
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        try:
            json.loads(body, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite_json")))
        except (ValueError, UnicodeError, RecursionError):
            await send({"type": "http.response.start", "status": 422,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": b'{"detail":"invalid_memory_json"}'})
            return
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class RememberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    subject_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    category: Literal["USER_FACT", "PREFERENCE", "PROJECT"] = "USER_FACT"
    content: str = Field(min_length=1, max_length=500)
    confirmed: Literal[True]

    @field_validator("subject_key")
    @classmethod
    def validate_subject(cls, value: str):
        if memory._contains_secret_like_content(value.replace(".", " ").replace("_", " ")):
            raise ValueError("secret_subject_not_permitted")
        return value

    @field_validator("confirmed", mode="before")
    @classmethod
    def validate_confirmation(cls, value):
        if value is not True:
            raise ValueError("explicit_boolean_confirmation_required")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str):
        value = value.strip()
        if not value or memory._contains_secret_like_content(value):
            raise ValueError("nonempty_nonsecret_memory_required")
        return value


class CorrectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content: str = Field(min_length=1, max_length=500)
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed: Literal[True]
    validate_content = field_validator("content")(RememberRequest.validate_content.__func__)
    validate_confirmation = field_validator("confirmed", mode="before")(RememberRequest.validate_confirmation.__func__)


class DeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed: Literal[True]
    validate_confirmation = field_validator("confirmed", mode="before")(RememberRequest.validate_confirmation.__func__)


def revision(row: dict) -> str:
    # Usage counters change during retrieval; they must not invalidate a user's
    # review. Hash only the editable record identity, content and status.
    fields = [str(row["memory_id"]), row["category"], row["subject_key"], row["content"], row["status"]]
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode()).hexdigest()


def public_record(row: dict) -> dict:
    return {"id": str(row["memory_id"]), "category": row["category"], "subject_key": row["subject_key"],
            "content": row["content"], "status": row["status"], "revision": revision(row),
            "created_at": row["created_at"].isoformat(), "updated_at": row["updated_at"].isoformat()}


def _require_revision(row: dict | None, expected: str):
    if row is None:
        raise HTTPException(404, "memory_not_found")
    if revision(row) != expected:
        raise HTTPException(409, "memory_changed_reload_before_confirming")


@router.get("")
def list_memories(page: int = Query(default=0, ge=0, le=10000),
                  status: Literal["ACTIVE", "SUPERSEDED", "ARCHIVED"] | None = None):
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT memory_id, category, subject_key, content, status, created_at, updated_at
                               FROM durable_memories WHERE user_id = %s AND (%s::text IS NULL OR status = %s)
                               ORDER BY created_at DESC, memory_id DESC LIMIT 51 OFFSET %s""",
                            (memory.DEFAULT_USER_ID, status, status, page * 50))
                rows = cur.fetchall()
        return {"records": [public_record(row) for row in rows[:50]], "page": page,
                "has_more": len(rows) > 50, "scope": "existing_local_user", "authenticated": False}
    except Exception:
        raise HTTPException(503, "memory_database_unavailable") from None


@router.post("", status_code=201)
def remember(request: RememberRequest):
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                # Serialize explicit creates for one subject. Legacy chat
                # promotion is a separate path; no new automatic inference.
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                            (str(memory.DEFAULT_USER_ID) + ":" + request.subject_key,))
                cur.execute("""SELECT memory_id FROM durable_memories
                               WHERE user_id = %s AND subject_key = %s AND status = 'ACTIVE' LIMIT 1""",
                            (memory.DEFAULT_USER_ID, request.subject_key))
                if cur.fetchone():
                    raise HTTPException(409, "active_subject_exists_review_and_correct_it")
                cur.execute("""INSERT INTO durable_memories
                               (memory_id, user_id, category, subject_key, content, normalized_content, confidence, status)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
                               RETURNING memory_id, category, subject_key, content, status, created_at, updated_at""",
                            (uuid.uuid4(), memory.DEFAULT_USER_ID, request.category, request.subject_key,
                             request.content, memory._normalize_text(request.content), 0.9))
                row = cur.fetchone()
        return {"record": public_record(row), "saved": True, "source": "explicit_user_confirmation"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "memory_database_unavailable") from None


@router.patch("/{memory_id}")
def correct(memory_id: uuid.UUID, request: CorrectRequest):
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM durable_memories WHERE memory_id = %s AND user_id = %s FOR UPDATE",
                            (memory_id, memory.DEFAULT_USER_ID))
                row = cur.fetchone()
                _require_revision(row, request.expected_revision)
                if row["status"] != "ACTIVE":
                    raise HTTPException(409, "only_active_memories_can_be_corrected")
                cur.execute("""UPDATE durable_memories SET content = %s, normalized_content = %s, updated_at = NOW()
                               WHERE memory_id = %s AND user_id = %s
                               RETURNING memory_id, category, subject_key, content, status, created_at, updated_at""",
                            (request.content, memory._normalize_text(request.content), memory_id, memory.DEFAULT_USER_ID))
                row = cur.fetchone()
        return {"record": public_record(row), "corrected": True}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "memory_database_unavailable") from None


@router.post("/{memory_id}/delete")
def delete(memory_id: uuid.UUID, request: DeleteRequest):
    try:
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM durable_memories WHERE memory_id = %s AND user_id = %s FOR UPDATE",
                            (memory_id, memory.DEFAULT_USER_ID))
                _require_revision(cur.fetchone(), request.expected_revision)
                cur.execute("DELETE FROM durable_memories WHERE memory_id = %s AND user_id = %s",
                            (memory_id, memory.DEFAULT_USER_ID))
        return {"deleted": True, "id": str(memory_id), "conversation_history_deleted": False}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "memory_database_unavailable") from None
