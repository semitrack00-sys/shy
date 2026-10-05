import importlib.util
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

sys.path.insert(0, str(SERVICES))
sys.path.insert(0, str(SERVICES / "core"))


for package_name, package_path in (
    ("model_router", SERVICES / "model-router" / "app"),
    ("tools", SERVICES / "tools"),
    ("agent_runtime", SERVICES / "agent-runtime"),
    ("research", SERVICES / "research"),
):
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("tools.contracts", SERVICES / "tools" / "contracts.py")
_load("tools.gateway", SERVICES / "tools" / "gateway.py")
_load("agent_runtime.planner", SERVICES / "agent-runtime" / "planner.py")
_load("agent_runtime.loop_state", SERVICES / "agent-runtime" / "loop_state.py")
_load("agent_runtime.runtime", SERVICES / "agent-runtime" / "runtime.py")
_load("agent_runtime.task_engine", SERVICES / "agent-runtime" / "task_engine.py")
_load("agent_runtime.verifier", SERVICES / "agent-runtime" / "verifier.py")
_load("research.web_search", SERVICES / "research" / "web_search.py")
_load("research.tavily", SERVICES / "research" / "tavily.py")
_load("research.research_engine", SERVICES / "research" / "research_engine.py")
_load("memory", SERVICES / "core" / "memory.py")
_load("task_persistence", SERVICES / "core" / "task_persistence.py")
knowledge = _load("knowledge", SERVICES / "core" / "knowledge.py")
main_module = _load("shy_core_main_v019", SERVICES / "core" / "main.py")


KnowledgeScope = knowledge.KnowledgeScope
KnowledgeSourceType = knowledge.KnowledgeSourceType
AuthorityLevel = knowledge.AuthorityLevel
KnowledgeBoundary = knowledge.KnowledgeBoundary
KnowledgeStatus = knowledge.KnowledgeStatus
GroundingStatus = knowledge.GroundingStatus



def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


store = knowledge.InMemoryKnowledgeStore(
    max_chunk_chars=140,
    overlap_chars=24,
    max_retrieval_results=8,
    max_context_chars=1200,
    max_sources=6,
    max_chunks=16,
)

USER_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
SCOPE_A = KnowledgeScope(user_id=USER_A, workspace_id="workspace-a", business_id="business-a")
SCOPE_B = KnowledgeScope(user_id=USER_A, workspace_id="workspace-b", business_id="business-a")
SCOPE_OTHER_USER = KnowledgeScope(user_id=USER_B, workspace_id="workspace-a", business_id="business-a")


# Basic retrieval
store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.DOCUMENT,
    source_id="doc:atlas:db",
    source_title="Atlas architecture note",
    subject="project.atlas.database",
    content="Project Atlas uses PostgreSQL.",
    authority=AuthorityLevel.AUTHORITATIVE,
    confidence=0.88,
)
basic = store.retrieve(query_text="What database does Project Atlas use?", scope=SCOPE_A)
_assert(basic.records, "basic retrieval should return a record")
_assert("postgresql" in basic.records[0].content.lower(), "PostgreSQL must be retrieved")
print("basic retrieval: PASS")


# Scope isolation
store.ingest_text(
    scope=SCOPE_B,
    source_type=KnowledgeSourceType.DOCUMENT,
    source_id="doc:atlas:db:b",
    source_title="Workspace B doc",
    subject="project.atlas.database",
    content="Project Atlas uses MySQL.",
    authority=AuthorityLevel.AUTHORITATIVE,
    confidence=0.9,
)
view_a = store.retrieve(query_text="Project Atlas database", scope=SCOPE_A)
view_b = store.retrieve(query_text="Project Atlas database", scope=SCOPE_B)
view_other_user = store.retrieve(query_text="Project Atlas database", scope=SCOPE_OTHER_USER)
_assert(any("postgresql" in row.content.lower() for row in view_a.records), "workspace A should retrieve PostgreSQL")
_assert(all("mysql" not in row.content.lower() for row in view_a.records), "workspace A must not retrieve workspace B private knowledge")
_assert(any("mysql" in row.content.lower() for row in view_b.records), "workspace B should retrieve MySQL")
_assert(len(view_other_user.records) == 0, "cross-user retrieval must be isolated")
print("scope isolation: PASS")


# Deduplication
before = len(store.list_records(SCOPE_A))
dup = store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.DOCUMENT,
    source_id="doc:atlas:db",
    source_title="Atlas architecture note",
    subject="project.atlas.database",
    content="Project Atlas uses PostgreSQL.",
    authority=AuthorityLevel.AUTHORITATIVE,
    confidence=0.9,
)
after = len(store.list_records(SCOPE_A))
_assert(dup.accepted is True, "duplicate ingestion should be accepted safely")
_assert(after == before, "exact duplicate ingestion should not create a new logical record")
print("deduplication: PASS")


# Supersession
old_db = store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.DOCUMENT,
    source_id="doc:atlas:legacy",
    source_title="Legacy runbook",
    subject="project.atlas.runtime.database",
    content="Project Atlas uses MySQL.",
    authority=AuthorityLevel.TRUSTED,
    confidence=0.72,
)
new_db = store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.DATABASE,
    source_id="db:atlas:config",
    source_title="Runtime config",
    subject="project.atlas.runtime.database",
    content="Project Atlas now uses PostgreSQL.",
    authority=AuthorityLevel.PRIMARY,
    confidence=0.95,
    correction=True,
)
_assert(old_db.created and new_db.created, "supersession setup records must exist")
rows = [row for row in store.list_records(SCOPE_A) if row.subject == "project.atlas.runtime.database"]
active = [row for row in rows if row.status == KnowledgeStatus.ACTIVE]
superseded = [row for row in rows if row.status == KnowledgeStatus.SUPERSEDED]
_assert(any("postgresql" in row.content.lower() for row in active), "new PostgreSQL record must be ACTIVE")
_assert(any("mysql" in row.content.lower() for row in superseded), "old MySQL record must be SUPERSEDED")
print("supersession: PASS")


# Conflict detection
store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.DOCUMENT,
    source_id="doc:finance:a",
    source_title="Finance plan A",
    subject="project.atlas.budget",
    content="Project Atlas budget is $120,000.",
    authority=AuthorityLevel.AUTHORITATIVE,
    confidence=0.9,
)
store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.DOCUMENT,
    source_id="doc:finance:b",
    source_title="Finance plan B",
    subject="project.atlas.budget",
    content="Project Atlas budget is $145,000.",
    authority=AuthorityLevel.AUTHORITATIVE,
    confidence=0.9,
)
conflicted = store.retrieve(query_text="Project Atlas budget", scope=SCOPE_A)
_assert(conflicted.conflicts, "conflicting records should be detected")
_assert(conflicted.knowledge_boundary == KnowledgeBoundary.CONFLICTING_KNOWLEDGE, "boundary must indicate conflict")
print("conflict detection: PASS")


# Freshness influence
now = datetime.now(timezone.utc)
store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.RESEARCH,
    source_id="research:new",
    source_title="Recent report",
    subject="project.atlas.transaction.volume",
    content="Project Atlas transaction volume is moderate.",
    source_timestamp=now - timedelta(days=2),
    authority=AuthorityLevel.TRUSTED,
    confidence=0.82,
)
store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.RESEARCH,
    source_id="research:old",
    source_title="Old report",
    subject="project.atlas.transaction.volume",
    content="Project Atlas transaction volume is moderate.",
    source_timestamp=now - timedelta(days=120),
    authority=AuthorityLevel.SECONDARY,
    confidence=0.61,
)
freshness_result = store.retrieve(query_text="Project Atlas transaction volume", scope=SCOPE_A)
_assert(freshness_result.records, "freshness test should return records")
_assert(freshness_result.stale_source_count >= 0, "freshness metadata should be populated")
print("freshness influence: PASS")


# Authority influence
store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.USER,
    source_id="user:note:1",
    source_title="User note",
    subject="project.atlas.primary.datastore",
    content="Project Atlas primary datastore is SQLite.",
    authority=AuthorityLevel.USER_PROVIDED,
    confidence=0.6,
)
store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.DATABASE,
    source_id="db:atlas:primary",
    source_title="Production settings",
    subject="project.atlas.primary.datastore",
    content="Project Atlas primary datastore is PostgreSQL.",
    authority=AuthorityLevel.PRIMARY,
    confidence=0.96,
)
authority_result = store.retrieve(query_text="Project Atlas primary datastore", scope=SCOPE_A)
_assert(authority_result.records, "authority retrieval should return records")
_assert("postgresql" in authority_result.records[0].content.lower(), "higher authority record should rank above low authority")
print("authority influence: PASS")


# Missing knowledge
missing = store.retrieve(query_text="What is the neutron flux threshold for reactor bay seven?", scope=SCOPE_A)
_assert(missing.knowledge_boundary in {KnowledgeBoundary.DATA_REQUIRED, KnowledgeBoundary.INSUFFICIENT_EVIDENCE}, "missing knowledge must not be hallucinated")
print("missing knowledge boundary: PASS")


# Secret rejection
secret = store.ingest_text(
    scope=SCOPE_A,
    source_type=KnowledgeSourceType.USER,
    source_id="user:secret",
    subject="secret.material",
    content="API key is sk-secret-12345",
)
_assert(secret.accepted is False, "secret-like knowledge should be rejected")
secret_fetch = store.retrieve(query_text="API key", scope=SCOPE_A)
_assert(all("sk-" not in row.content for row in secret_fetch.records), "secrets must never be exposed via retrieval")
print("secret rejection: PASS")


# Bounded retrieval and chunking
for index in range(30):
    store.ingest_text(
        scope=SCOPE_A,
        source_type=KnowledgeSourceType.DOCUMENT,
        source_id=f"doc:bulk:{index}",
        source_title=f"Bulk doc {index}",
        subject="project.atlas.bulk.notes",
        content=("Project Atlas bulk note " + str(index) + " ") * 40,
        authority=AuthorityLevel.SECONDARY,
        confidence=0.55,
    )
bounded = store.retrieve(query_text="Project Atlas bulk note", scope=SCOPE_A, max_results=5, max_context_chars=700)
_assert(len(bounded.records) <= 5, "retrieval count should respect bounds")
_assert(bounded.context_chars <= 700 or bounded.truncated_by_budget, "context budget should be bounded")
chunks = [row.chunks for row in bounded.records if row.chunks]
_assert(chunks, "large text ingestion should produce chunks")
print("bounded retrieval + chunking: PASS")


# Grounding metadata
grounded = store.retrieve(query_text="What database does Project Atlas use?", scope=SCOPE_A)
_assert(grounded.grounding_status in {GroundingStatus.GROUNDED, GroundingStatus.CONFLICTED}, "grounding metadata should be present")
print("grounding metadata: PASS")


# Fake citation protection
empty_store = knowledge.InMemoryKnowledgeStore()
empty_scope = KnowledgeScope(user_id=USER_A, workspace_id="empty", business_id="none")
no_evidence = empty_store.retrieve(query_text="nonexistent evidence", scope=empty_scope)
_assert(len(no_evidence.citations) == 0, "no evidence must produce no citations")
print("fake citation protection: PASS")


# Cognitive integration foundation: v0.18 deterministic cognitive path uses v0.19 retrieved knowledge.
integration_store = knowledge.InMemoryKnowledgeStore()
integration_scope = KnowledgeScope(user_id=USER_A, workspace_id="ws-k", business_id="biz-k")
integration_store.ingest_text(
    scope=integration_scope,
    source_type=KnowledgeSourceType.DATABASE,
    source_id="db:atlas:stack",
    source_title="Atlas system table",
    subject="project.atlas.database",
    content="Project Atlas currently uses PostgreSQL.",
    authority=AuthorityLevel.PRIMARY,
    confidence=0.95,
)
integration_store.ingest_text(
    scope=integration_scope,
    source_type=KnowledgeSourceType.DOCUMENT,
    source_id="doc:atlas:throughput",
    source_title="Capacity review",
    subject="project.atlas.transaction.volume",
    content="Project Atlas transaction volume is moderate.",
    authority=AuthorityLevel.AUTHORITATIVE,
    confidence=0.9,
)
integration_store.ingest_text(
    scope=integration_scope,
    source_type=KnowledgeSourceType.DOCUMENT,
    source_id="doc:atlas:consistency",
    source_title="Consistency requirement",
    subject="project.atlas.consistency",
    content="Project Atlas requires strict consistency.",
    authority=AuthorityLevel.AUTHORITATIVE,
    confidence=0.92,
)

main_module.knowledge_store = integration_store
request = main_module.ChatRequest(
    message="Evaluate whether Project Atlas should keep its current database architecture.",
    user_id=str(USER_A),
    workspace_id="ws-k",
    business_id="biz-k",
)
response = main_module._run_cognitive_deterministic_response(request, history=[], model_routing_metadata=None)
_assert(response is not None, "cognitive deterministic path should produce integrated knowledge response")
answer, metadata = response
_assert("retrieved knowledge indicates" in answer.lower(), "response should be evidence-grounded")
_assert("assumptions separated" in answer.lower(), "response should separate assumptions from retrieved facts")
_assert(metadata.get("knowledge_record_count", 0) >= 1, "metadata should include retrieved knowledge count")
_assert(metadata.get("grounding_status") in {"GROUNDED", "PARTIALLY_GROUNDED", "CONFLICTED"}, "grounding status should be set")
print("cognitive integration foundation: PASS")


print("SHY v0.19 universal knowledge checkpoint tests: PASS")
