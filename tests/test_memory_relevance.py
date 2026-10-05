import importlib.util
import uuid
from datetime import datetime, timedelta
from pathlib import Path


root = Path(__file__).resolve().parents[1]
memory_path = root / "services" / "core" / "memory.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


memory = load_module("shy_memory_phase6b", memory_path)

MemoryRecord = memory.MemoryRecord
MemoryQuery = memory.MemoryQuery
build_memory_query = memory.build_memory_query
select_memory_context = memory.select_memory_context
retrieve_memory_context = memory.retrieve_memory_context


USER_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER_B = uuid.UUID("00000000-0000-0000-0000-000000000002")
CONV_A1 = uuid.UUID("10000000-0000-0000-0000-000000000001")
CONV_A2 = uuid.UUID("10000000-0000-0000-0000-000000000002")
CONV_B1 = uuid.UUID("10000000-0000-0000-0000-000000000003")

NOW = datetime(2026, 9, 28, 11, 0, 0)

records = [
    MemoryRecord(
        message_id=uuid.UUID("20000000-0000-0000-0000-000000000001"),
        user_id=USER_A,
        conversation_id=CONV_A1,
        role="assistant",
        content="Payment reconciliation bug fix requires ledger rollback guard and idempotency key.",
        created_at=NOW - timedelta(days=9),
    ),
    MemoryRecord(
        message_id=uuid.UUID("20000000-0000-0000-0000-000000000002"),
        user_id=USER_A,
        conversation_id=CONV_A1,
        role="assistant",
        content="Lunch plans, weather, and unrelated chit chat.",
        created_at=NOW - timedelta(minutes=8),
    ),
    MemoryRecord(
        message_id=uuid.UUID("20000000-0000-0000-0000-000000000003"),
        user_id=USER_A,
        conversation_id=CONV_A2,
        role="assistant",
        content="React build failed due to tsconfig path alias mismatch.",
        created_at=NOW - timedelta(hours=2),
    ),
    MemoryRecord(
        message_id=uuid.UUID("20000000-0000-0000-0000-000000000004"),
        user_id=USER_A,
        conversation_id=CONV_A1,
        role="assistant",
        content="Payment reconciliation bug fix requires ledger rollback guard and idempotency key.",
        created_at=NOW - timedelta(days=8, minutes=1),
    ),
    MemoryRecord(
        message_id=uuid.UUID("20000000-0000-0000-0000-000000000005"),
        user_id=USER_A,
        conversation_id=CONV_A1,
        role="assistant",
        content="Policy says enable feature flag globally for rollout.",
        created_at=NOW - timedelta(days=3),
    ),
    MemoryRecord(
        message_id=uuid.UUID("20000000-0000-0000-0000-000000000006"),
        user_id=USER_A,
        conversation_id=CONV_A1,
        role="assistant",
        content="Policy says do NOT enable feature flag globally until approval.",
        created_at=NOW - timedelta(days=2),
    ),
    MemoryRecord(
        message_id=uuid.UUID("20000000-0000-0000-0000-000000000007"),
        user_id=USER_B,
        conversation_id=CONV_B1,
        role="assistant",
        content="User B payroll details and private account metadata.",
        created_at=NOW - timedelta(minutes=5),
    ),
]


q_invalid = MemoryQuery(
    query_text="",
    user_id=USER_A,
    conversation_id=CONV_A1,
    include_cross_conversation=False,
    max_results=3,
    max_context_chars=300,
    max_candidates=20,
)
invalid = select_memory_context(q_invalid, records)
assert invalid.query_valid is False
assert invalid.failure_reason == "INVALID_QUERY"
print("memory query validation: PASS")


q_rank = build_memory_query(
    query_text="payment reconciliation bug fix",
    conversation_id=CONV_A1,
    user_id=USER_A,
    include_cross_conversation=False,
    max_results=3,
    max_context_chars=800,
    max_candidates=30,
)
ranked = select_memory_context(q_rank, records)
assert ranked.selected_records
assert "Payment reconciliation bug fix" in ranked.selected_records[0].content
assert all("Lunch plans" not in item.content for item in ranked.selected_records)
print("relevance ranking and recency balance: PASS")


q_recent = build_memory_query(
    query_text="react build failed tsconfig",
    conversation_id=CONV_A1,
    user_id=USER_A,
    include_cross_conversation=True,
    max_results=3,
    max_context_chars=800,
    max_candidates=30,
)
recent = select_memory_context(q_recent, records)
assert recent.selected_records
assert recent.selected_records[0].conversation_id == CONV_A2
print("cross-conversation same-user retrieval: PASS")


first = select_memory_context(q_rank, records)
second = select_memory_context(q_rank, records)
assert first.selected_records == second.selected_records
print("stable deterministic ranking: PASS")


q_budget = build_memory_query(
    query_text="payment bug policy",
    conversation_id=CONV_A1,
    user_id=USER_A,
    include_cross_conversation=False,
    max_results=5,
    max_context_chars=120,
    max_candidates=30,
)
budgeted = select_memory_context(q_budget, records)
assert budgeted.context_chars >= 1
assert budgeted.context_chars <= max(len(item.content) for item in budgeted.selected_records)
assert budgeted.truncated_by_budget is True
print("context budget: PASS")


q_limit = build_memory_query(
    query_text="policy",
    conversation_id=CONV_A1,
    user_id=USER_A,
    include_cross_conversation=False,
    max_results=1,
    max_context_chars=1000,
    max_candidates=30,
)
limited = select_memory_context(q_limit, records)
assert len(limited.selected_records) == 1
assert limited.truncated_by_limit is True
print("result limit: PASS")


q_dedupe = build_memory_query(
    query_text="payment reconciliation bug",
    conversation_id=CONV_A1,
    user_id=USER_A,
    include_cross_conversation=False,
    max_results=5,
    max_context_chars=2000,
    max_candidates=30,
)
deduped = select_memory_context(q_dedupe, records)
payment_matches = [item for item in deduped.selected_records if "Payment reconciliation bug fix" in item.content]
assert len(payment_matches) == 1
print("conservative deduplication: PASS")


q_conflicts = build_memory_query(
    query_text="feature flag rollout policy",
    conversation_id=CONV_A1,
    user_id=USER_A,
    include_cross_conversation=False,
    max_results=5,
    max_context_chars=2000,
    max_candidates=30,
)
conflicts = select_memory_context(q_conflicts, records)
contents = [item.content for item in conflicts.selected_records]
assert any("enable feature flag" in item for item in contents)
assert any("do NOT enable feature flag" in item for item in contents)
print("conflicting memories preserved: PASS")


leak_check = build_memory_query(
    query_text="payroll details",
    conversation_id=CONV_A1,
    user_id=USER_A,
    include_cross_conversation=True,
    max_results=5,
    max_context_chars=2000,
    max_candidates=30,
)
leak_result = select_memory_context(leak_check, records)
assert all(item.user_id == USER_A for item in leak_result.selected_records)
print("user isolation: PASS")


same_conv_only = build_memory_query(
    query_text="react build failed",
    conversation_id=CONV_A1,
    user_id=USER_A,
    include_cross_conversation=False,
    max_results=5,
    max_context_chars=2000,
    max_candidates=30,
)
same_conv_result = select_memory_context(same_conv_only, records)
assert all(item.conversation_id == CONV_A1 for item in same_conv_result.selected_records)
print("conversation isolation policy: PASS")


empty_result = select_memory_context(q_rank, [])
assert empty_result.selected_records == ()
assert empty_result.failure_reason is None
print("empty memory safe behavior: PASS")


failed = retrieve_memory_context(q_rank, records_loader=lambda _q: (_ for _ in ()).throw(RuntimeError("db unavailable")))
assert failed.selected_records == ()
assert failed.failure_reason == "MEMORY_RETRIEVAL_FAILED"
print("retrieval failure safe behavior: PASS")

print("SHY Phase 6B memory relevance tests: PASS")
