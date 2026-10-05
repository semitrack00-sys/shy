import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from services.core.knowledge import (
    AuthorityLevel,
    KnowledgeScope,
    KnowledgeSourceType,
    PostgresKnowledgeStore,
)


def test_postgres_knowledge_survives_store_restart():
    user_id = str(uuid.uuid4())
    workspace_id = "ws-persist-1"
    business_id = "biz-persist-1"
    scope = KnowledgeScope(
        user_id=user_id,
        workspace_id=workspace_id,
        business_id=business_id,
        allow_public=False,
    )

    store = PostgresKnowledgeStore()
    result = store.ingest_text(
        scope=scope,
        source_type=KnowledgeSourceType.USER,
        source_id="source-1",
        subject="inventory policy",
        content="The inventory policy requires monthly reconciliation.",
        source_title="Ops Policy",
        source_timestamp=datetime(2025, 1, 7, tzinfo=timezone.utc),
        authority=AuthorityLevel.AUTHORITATIVE,
        confidence=0.92,
    )
    assert result.accepted

    restarted = PostgresKnowledgeStore()
    retrieved = restarted.retrieve(
        query_text="monthly reconciliation inventory policy",
        scope=scope,
        max_results=4,
        max_context_chars=1200,
        max_sources=4,
    )

    assert retrieved.records
    assert any("inventory" in record.subject for record in retrieved.records)
    assert any("monthly reconciliation" in record.content for record in retrieved.records)

    dedup = restarted.ingest_text(
        scope=scope,
        source_type=KnowledgeSourceType.USER,
        source_id="source-1",
        subject="inventory policy",
        content="The inventory policy requires monthly reconciliation.",
        source_title="Ops Policy",
        source_timestamp=datetime(2025, 1, 7, tzinfo=timezone.utc),
        authority=AuthorityLevel.AUTHORITATIVE,
        confidence=0.92,
    )
    assert dedup.accepted is True
    assert dedup.duplicate_of is not None

    assert len(restarted.list_records(scope)) == 1


def test_postgres_dedup_is_atomic_under_concurrency():
    user_id = str(uuid.uuid4())
    workspace_id = "ws-concurrency-1"
    business_id = "biz-concurrency-1"
    scope = KnowledgeScope(
        user_id=user_id,
        workspace_id=workspace_id,
        business_id=business_id,
        allow_public=False,
    )

    def ingest_once() -> tuple[bool, uuid.UUID | None, str | None]:
        store = PostgresKnowledgeStore()
        result = store.ingest_text(
            scope=scope,
            source_type=KnowledgeSourceType.DOCUMENT,
            source_id="durable-atomic-source",
            subject="ops.concurrent.policy",
            content="The policy requires monthly reconciliation.",
            source_title="Ops Policy",
            source_timestamp=datetime(2025, 1, 7, tzinfo=timezone.utc),
            authority=AuthorityLevel.AUTHORITATIVE,
            confidence=0.92,
        )
        return result.accepted, result.duplicate_of, result.rejected_reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: ingest_once(), range(2)))

    assert sum(1 for accepted, _, _ in outcomes if accepted) >= 1
    assert sum(1 for _, duplicate_of, _ in outcomes if duplicate_of is not None) >= 1

    store = PostgresKnowledgeStore()
    rows = store.list_records(scope)
    assert len(rows) == 1
    row = rows[0]
    assert row.source_id == "durable-atomic-source"
    assert row.subject == "ops.concurrent.policy"
    assert row.content == "The policy requires monthly reconciliation."
    assert len(row.chunks) == 1
    assert row.provenance.source_id == "durable-atomic-source"
    assert row.provenance.content_hash == row.content_hash
