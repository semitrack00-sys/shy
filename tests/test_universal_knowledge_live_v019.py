import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx


BASE_URL = os.getenv("SHY_API_BASE_URL", "http://127.0.0.1:8019").rstrip("/")
TIMEOUT = 240.0



def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)



def _safe_get(path: str):
    try:
        return httpx.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
    except Exception:
        return None



def _post(path: str, payload: dict, expected_status: int = 200) -> dict:
    response = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=TIMEOUT)
    if response.status_code != expected_status:
        raise AssertionError(f"{path} expected {expected_status}, got {response.status_code}: {response.text}")
    return response.json() if response.content else {}



def _chat(message: str, **extra) -> dict:
    payload = {"message": message}
    payload.update(extra)
    return _post("/chat", payload)



def _scope(workspace: str, business: str, user: str) -> dict:
    return {
        "workspace_id": workspace,
        "business_id": business,
        "user_id": user,
    }



def _ingest(scope_payload: dict, **fields) -> dict:
    payload = dict(scope_payload)
    payload.update(fields)
    return _post("/testing/knowledge/ingest", payload)



def _retrieve(scope_payload: dict, query_text: str, **kwargs) -> dict:
    payload = dict(scope_payload)
    payload["query_text"] = query_text
    payload.update(kwargs)
    return _post("/testing/knowledge/retrieve", payload)



def _records(scope_payload: dict) -> dict:
    return _post("/testing/knowledge/records", dict(scope_payload))



def _reset_store():
    _post("/testing/knowledge/reset", {})



def _citations_map_to_records(result: dict) -> bool:
    record_ids = {row["knowledge_id"] for row in result.get("records", [])}
    return all(item.get("knowledge_id") in record_ids for item in result.get("citations", []))



def main():
    health_probe = _safe_get("/health")
    if health_probe is None or health_probe.status_code != 200:
        print("SKIP: live v0.19 runtime on :8019 is not available")
        return

    health = health_probe.json()
    _assert(health.get("status") == "ok", "health status must be ok")
    _assert(bool(health.get("application_healthy")), "application must be healthy")
    _assert(bool(health.get("ollama_connected")), "ollama must be connected")
    _assert(bool(health.get("database_connected")), "database must be connected")
    _assert(bool(health.get("local_model_available")), "local model must be available")
    _assert(health.get("version") == "0.19.0", "version must be 0.19.0")
    print("live health/version: PASS")

    capabilities = _safe_get("/testing/knowledge/capabilities")
    _assert(capabilities is not None and capabilities.status_code == 200, "knowledge test hooks must be enabled")
    caps = capabilities.json()
    _assert(caps.get("persistence_mode") == "in_memory", "checkpoint persistence mode must be in_memory")

    _reset_store()

    base_user = f"v019-live-user-{uuid.uuid4().hex[:8]}"
    base_scope = _scope("v019-live-ws-a", "v019-live-biz-a", base_user)

    # 2. Live ingestion and retrieval proof.
    ingest_result = _ingest(
        base_scope,
        source_type="DOCUMENT",
        source_id="doc:atlas:db:live",
        source_title="Atlas runbook",
        subject="project.atlas.database",
        content="Project Atlas uses PostgreSQL for its database.",
        authority="AUTHORITATIVE",
        confidence=0.9,
    )
    _assert(ingest_result.get("accepted") is True, "knowledge ingestion must be accepted")

    direct = _retrieve(base_scope, "What database does Project Atlas use?")
    _assert(direct.get("knowledge_record_count", 0) > 0, "retrieval must return records")
    _assert(any("postgresql" in row.get("content", "").lower() for row in direct.get("records", [])), "retrieval must contain PostgreSQL")
    _assert(direct.get("grounding_status") == "GROUNDED", "grounding status must be GROUNDED")
    _assert(direct.get("citation_integrity") is True and _citations_map_to_records(direct), "citation/source references must map to real records")
    _assert(direct.get("citations"), "at least one citation/source reference is required")
    print("knowledge ingestion + retrieval/provenance/grounding: PASS")

    # Also prove chat answer is from knowledge, not only same-conversation history.
    chat_query = _chat("What database does Project Atlas use?", **base_scope)
    msg = str(chat_query.get("message", "")).lower()
    cognitive = chat_query.get("cognitive", {})
    _assert("postgresql" in msg, "chat answer must state PostgreSQL")
    _assert(int(cognitive.get("knowledge_record_count", 0)) > 0, "chat metadata must report knowledge retrieval")
    _assert(cognitive.get("grounding_status") == "GROUNDED", "chat grounding status must be GROUNDED")

    # 3. Cross-conversation retrieval.
    seed_a = _chat("Project Atlas uses PostgreSQL.", **base_scope)
    conv_a = seed_a.get("conversation_id")
    _assert(bool(conv_a), "conversation A must exist")
    convo_b = _chat("What database does Project Atlas use?", **base_scope)
    _assert("postgresql" in str(convo_b.get("message", "")).lower(), "conversation B should retrieve PostgreSQL")
    _assert(int((convo_b.get("cognitive") or {}).get("knowledge_record_count", 0)) > 0, "cross-conversation retrieval must use knowledge store")
    print("cross-conversation retrieval: PASS")

    # 4. Scope isolation including cross-user.
    scope_a = _scope("iso-ws-a", "iso-biz", "iso-user-a")
    scope_b = _scope("iso-ws-b", "iso-biz", "iso-user-a")
    scope_user_b = _scope("iso-ws-a", "iso-biz", "iso-user-b")

    _ingest(scope_a, source_type="DOCUMENT", source_id="doc:iso:a", subject="project.atlas.database", content="Project Atlas uses PostgreSQL.", authority="AUTHORITATIVE")
    _ingest(scope_b, source_type="DOCUMENT", source_id="doc:iso:b", subject="project.atlas.database", content="Project Atlas uses MySQL.", authority="AUTHORITATIVE")

    a_res = _retrieve(scope_a, "What database does Project Atlas use?")
    b_res = _retrieve(scope_b, "What database does Project Atlas use?")
    user_b_res = _retrieve(scope_user_b, "What database does Project Atlas use?")

    _assert(any("postgresql" in row.get("content", "").lower() for row in a_res.get("records", [])), "workspace A must retrieve PostgreSQL")
    _assert(all("mysql" not in row.get("content", "").lower() for row in a_res.get("records", [])), "workspace A must not leak workspace B")
    _assert(any("mysql" in row.get("content", "").lower() for row in b_res.get("records", [])), "workspace B must retrieve MySQL")
    _assert(int(user_b_res.get("knowledge_record_count", 0)) == 0, "cross-user retrieval must be isolated")
    print("scope/user isolation: PASS")

    # 5. Deduplication live.
    dedupe_scope = _scope("dedupe-ws", "dedupe-biz", "dedupe-user")
    for _ in range(4):
        _ingest(
            dedupe_scope,
            source_type="DOCUMENT",
            source_id="doc:dedupe:atlas",
            subject="project.atlas.database",
            content="Project Atlas uses PostgreSQL.",
            authority="AUTHORITATIVE",
        )
    dedupe_records = _records(dedupe_scope)
    active_claims = [
        row for row in dedupe_records.get("records", [])
        if row.get("subject") == "project.atlas.database" and row.get("status") == "ACTIVE"
    ]
    _assert(len(active_claims) == 1, "duplicate ingestion must keep one logical active fact")
    print("deduplication live: PASS")

    # 6. Supersession.
    sup_scope = _scope("sup-ws", "sup-biz", "sup-user")
    _ingest(sup_scope, source_type="DOCUMENT", source_id="doc:sup:old", subject="project.atlas.database", content="Project Atlas uses MySQL.", authority="TRUSTED")
    _ingest(sup_scope, source_type="DOCUMENT", source_id="doc:sup:new", subject="project.atlas.database", content="Project Atlas now uses PostgreSQL.", authority="AUTHORITATIVE", correction=True)
    sup_records = _records(sup_scope).get("records", [])
    _assert(any(row.get("status") == "SUPERSEDED" and "mysql" in row.get("content", "").lower() for row in sup_records), "old MySQL record must be SUPERSEDED")
    _assert(any(row.get("status") == "ACTIVE" and "postgresql" in row.get("content", "").lower() for row in sup_records), "new PostgreSQL record must be ACTIVE")
    sup_query = _chat("What database does Project Atlas use?", **sup_scope)
    _assert("postgresql" in str(sup_query.get("message", "")).lower(), "retrieval should return PostgreSQL as current")
    print("supersession live: PASS")

    # 7. Conflict live proof.
    conflict_scope = _scope("conflict-ws", "conflict-biz", "conflict-user")
    _ingest(conflict_scope, source_type="DOCUMENT", source_id="doc:rev:a", source_title="Report A", subject="finance.q3.revenue", content="Q3 revenue was $120,000.", authority="AUTHORITATIVE")
    _ingest(conflict_scope, source_type="DOCUMENT", source_id="doc:rev:b", source_title="Report B", subject="finance.q3.revenue", content="Q3 revenue was $145,000.", authority="AUTHORITATIVE")
    conflict = _retrieve(conflict_scope, "What was Q3 revenue?")
    _assert(conflict.get("knowledge_boundary") == "CONFLICTING_KNOWLEDGE", "knowledge boundary must indicate conflict")
    _assert(conflict.get("grounding_status") == "CONFLICTED", "grounding should be CONFLICTED")
    _assert(conflict.get("conflict_count", 0) > 0, "conflict must be detected")
    conflict_chat = _chat("What was Q3 revenue?", **conflict_scope)
    conflict_msg = str(conflict_chat.get("message", "")).lower()
    _assert("disagree" in conflict_msg or "conflict" in conflict_msg, "final response must explicitly explain disagreement")
    print("conflict handling live: PASS")

    # 8. Authority ranking with conflict preserved.
    authority_scope = _scope("authority-ws", "authority-biz", "authority-user")
    _ingest(authority_scope, source_type="DOCUMENT", source_id="doc:budget:secondary", source_title="Secondary plan", subject="project.atlas.budget", content="Project Atlas budget is $120,000.", authority="SECONDARY", confidence=0.7)
    _ingest(authority_scope, source_type="DATABASE", source_id="db:budget:authoritative", source_title="Authoritative finance DB", subject="project.atlas.budget", content="Project Atlas budget is $145,000.", authority="AUTHORITATIVE", confidence=0.95)
    auth = _retrieve(authority_scope, "What is Project Atlas budget?")
    _assert(auth.get("records"), "authority retrieval requires records")
    _assert("145,000" in auth["records"][0].get("content", ""), "authoritative source should rank higher")
    _assert(auth.get("conflict_count", 0) > 0, "authority must not erase conflict visibility")
    auth_chat = _chat("What is Project Atlas budget?", **authority_scope)
    auth_msg = str(auth_chat.get("message", "")).lower()
    _assert("strongest" in auth_msg or "favors" in auth_msg or "conflict" in auth_msg, "response should explain stronger evidence and disagreement")
    print("authority ranking live: PASS")

    # 9. Freshness ranking with unresolved conflict.
    freshness_scope = _scope("fresh-ws", "fresh-biz", "fresh-user")
    older_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    newer_ts = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    _ingest(freshness_scope, source_type="DOCUMENT", source_id="doc:launch:old", source_title="Old roadmap", source_timestamp=older_ts, subject="project.atlas.launch.date", content="Project Atlas launch date is November 1.", authority="TRUSTED")
    _ingest(freshness_scope, source_type="DOCUMENT", source_id="doc:launch:new", source_title="Recent roadmap", source_timestamp=newer_ts, subject="project.atlas.launch.date", content="Project Atlas launch date is November 15.", authority="TRUSTED")
    fresh = _retrieve(freshness_scope, "What is Project Atlas launch date?")
    _assert(fresh.get("records"), "freshness retrieval requires records")
    _assert("november 15" in fresh["records"][0].get("content", "").lower(), "newer source should rank higher")
    _assert(fresh.get("conflict_count", 0) > 0, "independent conflicting dates must remain conflicted")
    print("freshness ranking live: PASS")

    # 10. Missing knowledge behavior.
    missing_scope = _scope("missing-ws", "missing-biz", "missing-user")
    missing_chat = _chat("What is Project Mercury's database?", **missing_scope)
    missing_cognitive = missing_chat.get("cognitive", {})
    _assert((missing_cognitive.get("knowledge_boundary") in {"DATA_REQUIRED", "INSUFFICIENT_EVIDENCE"}), "missing knowledge boundary must be DATA_REQUIRED/INSUFFICIENT_EVIDENCE")
    _assert(missing_cognitive.get("grounding_status") != "GROUNDED", "missing knowledge must not be marked GROUNDED")
    _assert(not missing_cognitive.get("knowledge_used"), "missing knowledge must not emit fake citations")
    print("missing knowledge behavior: PASS")

    # 11. Secret rejection.
    secret_scope = _scope("secret-ws", "secret-biz", "secret-user")
    secret_samples = [
        "API key is sk-test-12345",
        "password=demo-pass",
        "private token: token=abc123",
        "private key -----BEGIN PRIVATE KEY-----",
        "approval token is tok-approval-000",
    ]
    for index, sample in enumerate(secret_samples):
        outcome = _ingest(secret_scope, source_type="USER", source_id=f"secret:{index}", subject="secrets.test", content=sample)
        _assert(outcome.get("accepted") is False, "secret-like values must be rejected")
    secret_retrieved = _retrieve(secret_scope, "API key password token private key")
    _assert(secret_retrieved.get("knowledge_record_count", 0) == 0, "secret records must not be retrievable")
    print("secret rejection live: PASS")

    # 12. Large source chunking.
    chunk_scope = _scope("chunk-ws", "chunk-biz", "chunk-user")
    long_text = " ".join([f"Project Atlas clause {i}: maintain strong consistency and moderate traffic assumptions." for i in range(1, 260)])
    chunk_ingest = _ingest(
        chunk_scope,
        source_type="DOCUMENT",
        source_id="doc:chunk:1",
        source_title="Long architecture brief",
        subject="project.atlas.architecture.long",
        content=long_text,
        authority="TRUSTED",
    )
    _assert(chunk_ingest.get("created"), "long source must create record")
    created = chunk_ingest["created"][0]
    chunks = created.get("chunks", [])
    _assert(len(chunks) > 1, "long source must be chunked")
    _assert(len(chunks) <= 24, "maximum chunk count must be enforced")
    orders = [item.get("order_index") for item in chunks]
    _assert(orders == sorted(orders), "chunk order must be stable")
    _assert(len({item.get("chunk_id") for item in chunks}) == len(chunks), "chunk IDs must be stable/unique")
    _assert(all(item.get("length", 0) <= 320 for item in chunks), "chunk size must be bounded")
    print("large-source chunking: PASS")

    # 13. Bounded retrieval.
    bounds_scope = _scope("bounds-ws", "bounds-biz", "bounds-user")
    for i in range(35):
        _ingest(
            bounds_scope,
            source_type="DOCUMENT",
            source_id=f"doc:bounds:{i}",
            source_title=f"Bounds source {i}",
            subject="project.atlas.bulk",
            content=f"Project Atlas bounded retrieval record {i} with deterministic content and evidence.",
            authority="SECONDARY",
        )
    bounded = _retrieve(bounds_scope, "Project Atlas bounded retrieval record", max_results=5, max_context_chars=450, max_sources=3)
    _assert(len(bounded.get("records", [])) <= 5, "record limit must be enforced")
    _assert(bounded.get("source_count", 0) <= 3, "source limit must be enforced")
    _assert(bounded.get("context_chars", 0) <= 450 or bounded.get("truncated_by_budget"), "context budget must be enforced")
    print("bounded retrieval live: PASS")

    # 14. Cognitive integration.
    cog_scope = _scope("cog-ws", "cog-biz", "cog-user")
    _ingest(cog_scope, source_type="DOCUMENT", source_id="doc:cog:db", subject="project.atlas.database", content="Project Atlas uses PostgreSQL.", authority="AUTHORITATIVE")
    _ingest(cog_scope, source_type="DOCUMENT", source_id="doc:cog:consistency", subject="project.atlas.consistency", content="Project Atlas requires strong transactional consistency.", authority="AUTHORITATIVE")
    _ingest(cog_scope, source_type="DOCUMENT", source_id="doc:cog:traffic", subject="project.atlas.traffic", content="Project Atlas currently has moderate traffic.", authority="TRUSTED")
    _ingest(cog_scope, source_type="DOCUMENT", source_id="doc:cog:team", subject="project.atlas.team", content="Project Atlas is maintained by a small engineering team.", authority="TRUSTED")

    cog = _chat("Should Project Atlas move to microservices now, or remain on a simpler architecture?", **cog_scope)
    cog_msg = str(cog.get("message", "")).lower()
    cog_meta = cog.get("cognitive", {})
    _assert(int(cog_meta.get("knowledge_record_count", 0)) > 0, "cognitive flow must use retrieved knowledge")
    _assert(cog_meta.get("grounding_status") in {"GROUNDED", "PARTIALLY_GROUNDED", "CONFLICTED"}, "grounding metadata must be present")
    _assert("retrieved knowledge" in cog_msg or "constraints" in cog_msg, "answer should materially use retrieved facts")
    _assert("assumptions" in cog_msg and "uncertainty" in cog_msg, "answer should separate assumptions and uncertainty")
    _assert(bool(cog_meta.get("critic_invoked")), "critic should be invoked")
    _assert(bool(cog_meta.get("verifier_invoked")), "verifier should be invoked")
    print("cognitive integration live: PASS")

    # 15. Contradiction integration.
    contradiction_scope = _scope("contradiction-ws", "contradiction-biz", "contradiction-user")
    _ingest(contradiction_scope, source_type="DOCUMENT", source_id="doc:contradict:a", subject="finance.q3.revenue", content="Q3 revenue was $120,000.", authority="AUTHORITATIVE")
    _ingest(contradiction_scope, source_type="DOCUMENT", source_id="doc:contradict:b", subject="finance.q3.revenue", content="Q3 revenue was $145,000.", authority="AUTHORITATIVE")
    contradiction = _chat("Given the current Q3 revenue, should we increase hiring now?", **contradiction_scope)
    contradiction_meta = contradiction.get("cognitive", {})
    contradiction_msg = str(contradiction.get("message", "")).lower()
    _assert(contradiction_meta.get("conflict_count", 0) > 0, "conflict must propagate into cognitive metadata")
    _assert(contradiction_meta.get("grounding_status") == "CONFLICTED", "grounding should reflect conflict")
    _assert("conflict" in contradiction_msg or "disagree" in contradiction_msg or "uncertain" in contradiction_msg, "response must not treat conflict as certain")
    print("contradiction integration: PASS")

    # 16. Grounding + citation integrity.
    grounded = _retrieve(cog_scope, "Project Atlas architecture consistency")
    _assert("knowledge_used" not in grounded, "testing retrieval should expose explicit records/citations, not fake fields")
    _assert(_citations_map_to_records(grounded), "every citation must map to a real record")
    _assert(all(item.get("provenance", {}).get("content_hash") for item in grounded.get("records", [])), "provenance content hash required")
    print("grounding + citation integrity: PASS")

    # 17. Restart/non-durability classification (checkpoint truth).
    # Live test asserts capabilities; operator runbook performs actual restart sequence.
    _assert(caps.get("persistence_mode") == "in_memory", "checkpoint must classify store as non-durable")
    print("restart persistence classification: EXPECTED CHECKPOINT GAP: NON-DURABLE KNOWLEDGE STORE")

    # 18. Memory vs knowledge separation (no automatic merge).
    mem_scope = _scope("mem-vs-know-ws", "mem-vs-know-biz", "mem-vs-know-user")
    _chat("My company is Contoso Dynamics.", **mem_scope)
    mem_knowledge_records = _records(mem_scope)
    _assert(mem_knowledge_records.get("count", 0) == 0, "memory records should not auto-duplicate into knowledge store")
    print("memory vs knowledge separation: PASS")

    # 19. Tool-output knowledge behavior.
    tool_scope = _scope("tool-ws", "tool-biz", "tool-user")
    tool_ingest = _ingest(
        tool_scope,
        source_type="TOOL",
        source_id="tool:calculator:run-1",
        source_title="calculator",
        subject="project.atlas.financial.ratio",
        content="Calculated ratio result = 0.42",
        authority="AUTHORITATIVE",
        confidence=0.85,
    )
    _assert(tool_ingest.get("accepted") is True, "trusted tool ingestion should be accepted")
    tool_ret = _retrieve(tool_scope, "financial ratio")
    _assert(tool_ret.get("records"), "tool knowledge should be retrievable")
    _assert(tool_ret["records"][0].get("source_type") == "TOOL", "source_type must be TOOL")
    _assert(tool_ret["records"][0].get("provenance", {}).get("source_title") == "calculator", "provenance should include tool identity")
    print("tool-output knowledge behavior: PASS")

    # 20. Provenance inspection.
    provenance_result = _retrieve(base_scope, "Project Atlas database")
    _assert(provenance_result.get("records"), "provenance inspection requires records")
    row = provenance_result["records"][0]
    prov = row.get("provenance", {})
    _assert(prov.get("source_type"), "provenance source_type required")
    _assert(prov.get("source_id"), "provenance source_id required")
    _assert("retrieved_at" in prov and prov.get("retrieved_at"), "provenance retrieval timestamp required")
    _assert(prov.get("authority"), "provenance authority required")
    _assert(prov.get("content_hash"), "provenance content hash required")
    print("provenance inspection: PASS")

    print("SHY v0.19 live universal knowledge gate 1 tests: PASS")


if __name__ == "__main__":
    main()
