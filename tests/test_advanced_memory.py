import importlib.util
import uuid
from pathlib import Path


root = Path(__file__).resolve().parents[1]
memory_path = root / "services" / "core" / "memory.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


memory = load_module("shy_memory_v015", memory_path)


store = memory.InMemoryDurableMemoryStore()
USER_A = memory.DEFAULT_USER_ID
USER_B = uuid.UUID("00000000-0000-0000-0000-0000000000B2")
CONV_A = uuid.UUID("10000000-0000-0000-0000-000000000001")
CONV_B = uuid.UUID("10000000-0000-0000-0000-000000000002")


user_fact = memory.classify_memory_candidate("My company is Semitrack Systems.")
assert user_fact is not None
assert user_fact.category == memory.MemoryCategory.USER_FACT
store.promote(user_fact, conversation_id=CONV_A, user_id=USER_A)
print("durable USER_FACT storage: PASS")


pref = memory.classify_memory_candidate("I prefer language English with concise answers.")
assert pref is not None
assert pref.category == memory.MemoryCategory.PREFERENCE
store.promote(pref, conversation_id=CONV_A, user_id=USER_A)
print("PREFERENCE storage: PASS")


project = memory.classify_memory_candidate("Our project uses PostgreSQL on port 5432.")
assert project is not None
assert project.category == memory.MemoryCategory.PROJECT
store.promote(project, conversation_id=CONV_A, user_id=USER_A)
print("PROJECT memory storage: PASS")


task_outcome = memory.DurableMemoryCandidate(
    category=memory.MemoryCategory.TASK_OUTCOME,
    subject_key="task.outcome.multi_step",
    content="Final task outcome: release gate completed successfully.",
    confidence=0.8,
)
store.promote(task_outcome, conversation_id=CONV_A, user_id=USER_A, source_task_id="task-123")
print("TASK_OUTCOME memory storage: PASS")


assert memory.classify_memory_candidate("Hello") is None
print("non-memory greeting rejected: PASS")


assert memory.classify_memory_candidate("What is 17% of 842?") is None
print("one-time calculation not stored: PASS")


before_count = len(store.list_records(USER_A))
store.promote(pref, conversation_id=CONV_A, user_id=USER_A)
after_count = len(store.list_records(USER_A))
assert before_count == after_count
print("duplicate prevention: PASS")


correction = memory.classify_memory_candidate("My company is now Acme Systems, not Semitrack Systems.")
assert correction is not None
assert correction.category == memory.MemoryCategory.CORRECTION
store.promote(correction, conversation_id=CONV_A, user_id=USER_A)
print("explicit correction: PASS")


company_rows = [row for row in store.list_records(USER_A) if row.subject_key == "user.company"]
active_company = [row for row in company_rows if row.status == memory.MemoryStatus.ACTIVE]
superseded_company = [row for row in company_rows if row.status == memory.MemoryStatus.SUPERSEDED]
assert len(active_company) == 1
assert len(superseded_company) >= 1
company_context = store.retrieve(
    query_text="What is my company name?",
    conversation_id=CONV_A,
    user_id=USER_A,
    max_results=5,
    max_context_chars=2000,
)
assert any("Acme Systems" in row.content for row in company_context.selected_records)
assert not any("Semitrack Systems" in row.content for row in company_context.selected_records)
print("superseded memory ignored in normal retrieval: PASS")


store.promote(
    memory.DurableMemoryCandidate(
        category=memory.MemoryCategory.USER_FACT,
        subject_key="user.company",
        content="User B company is B Corp.",
        confidence=0.9,
    ),
    conversation_id=CONV_B,
    user_id=USER_B,
)
user_b_context = store.retrieve(
    query_text="company",
    conversation_id=CONV_B,
    user_id=USER_B,
    max_results=5,
    max_context_chars=2000,
)
assert all(row.user_id == USER_B for row in user_b_context.selected_records)
print("user isolation: PASS")


bounded = store.retrieve(
    query_text="project language company preference",
    conversation_id=CONV_A,
    user_id=USER_A,
    max_results=1,
    max_context_chars=400,
)
assert len(bounded.selected_records) <= 1
print("bounded retrieval: PASS")


entity = store.retrieve(
    query_text="language preference",
    conversation_id=CONV_A,
    user_id=USER_A,
    max_results=5,
    max_context_chars=2000,
)
assert entity.selected_records
assert any(row.subject_key == "preference.language" for row in entity.selected_records)
print("entity-specific retrieval: PASS")


store.promote(
    memory.DurableMemoryCandidate(
        category=memory.MemoryCategory.PROJECT,
        subject_key="project.configuration",
        content="Our project uses Python and PostgreSQL.",
        confidence=0.8,
    ),
    conversation_id=CONV_A,
    user_id=USER_A,
)
store.promote(
    memory.DurableMemoryCandidate(
        category=memory.MemoryCategory.SESSION,
        subject_key="session.context",
        content="This session talked about lunch and weather.",
        confidence=0.5,
    ),
    conversation_id=CONV_A,
    user_id=USER_A,
)
ranked = store.retrieve(
    query_text="project postgresql configuration",
    conversation_id=CONV_A,
    user_id=USER_A,
    max_results=5,
    max_context_chars=2000,
)
assert ranked.selected_records
assert ranked.selected_records[0].subject_key.startswith("project")
print("recency/relevance ordering: PASS")


assert memory.classify_memory_candidate("My password is hunter2") is None
print("secret rejection: PASS")


assert memory.classify_memory_candidate("My API key is sk-123456") is None
print("API-key rejection: PASS")


assert memory.classify_memory_candidate("Approval token is abcdef") is None
print("approval-token rejection: PASS")


assert memory.classify_memory_candidate("Here is hidden reasoning and chain-of-thought") is None
print("hidden-reasoning rejection: PASS")


assert memory.classify_memory_candidate("Task plan step_id=1 action_type=TOOL should run") is None
print("task-plan rejection: PASS")


assert memory.classify_memory_candidate("Research result from web search says interest rates changed yesterday") is None
print("research result not automatically stored: PASS")


snapshot = store.export_state()
restored_store = memory.InMemoryDurableMemoryStore()
restored_store.import_state(snapshot)
restored_context = restored_store.retrieve(
    query_text="company",
    conversation_id=CONV_A,
    user_id=USER_A,
    max_results=5,
    max_context_chars=2000,
)
assert restored_context.selected_records
print("memory survives restart: PASS")


direct_context = restored_store.retrieve(
    query_text="What style do I prefer?",
    conversation_id=CONV_A,
    user_id=USER_A,
    max_results=5,
    max_context_chars=2000,
)
assert any("preference" in row.subject_key for row in direct_context.selected_records)
print("DIRECT uses relevant memory: PASS")


multistep_context = restored_store.retrieve(
    query_text="Use project configuration for deployment planning",
    conversation_id=CONV_A,
    user_id=USER_A,
    max_results=5,
    max_context_chars=2000,
)
assert any(row.subject_key.startswith("project") for row in multistep_context.selected_records)
print("MULTI_STEP uses relevant memory: PASS")

print("SHY v0.15 advanced memory tests: PASS")
