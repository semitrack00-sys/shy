import os
import uuid

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://shy:shy_local_dev@host.docker.internal:5432/shy"
)

DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def connect():
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
