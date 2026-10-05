import os

import httpx


BASE_URL = os.getenv("SHY_API_BASE_URL", "http://127.0.0.1:8020").rstrip("/")
TIMEOUT = 60.0


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _chat(message: str) -> dict:
    response = httpx.post(
        f"{BASE_URL}/chat",
        json={
            "message": message,
            "workspace_id": "v020-expert-ws",
            "business_id": "v020-expert-biz",
            "user_id": "v020-expert-user",
        },
        timeout=TIMEOUT,
    )
    _assert(response.status_code == 200, f"chat expected 200, got {response.status_code}: {response.text}")
    return response.json()


health = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
_assert(health.status_code == 200, f"health expected 200, got {health.status_code}")
health_payload = health.json()
_assert(health_payload.get("version") == "0.20.0", "live runtime must report SHY v0.20.0")
_assert(health_payload.get("application_healthy") is True, "v0.20 runtime must be healthy")
_assert(health_payload.get("database_connected") is True, "PostgreSQL must be connected")
_assert(health_payload.get("ollama_connected") is True, "Ollama must be connected")
_assert(health_payload.get("local_model_available") is True, "configured local model must be available")
print("SHY v0.20 live health: PASS")


software = _chat(
    "Compare PostgreSQL and MySQL for a software architecture and recommend the safer tradeoffs."
)
_assert(software.get("status") == "RESPOND", f"software expert chat must respond: {software}")
cognitive = software.get("cognitive") or {}
expert = cognitive.get("expert") or {}
_assert(expert.get("domain") == "SOFTWARE_ENGINEERING", f"expected software domain, got {expert}")
_assert(expert.get("risk_level") == "MEDIUM", f"software recommendation should be medium risk: {expert}")
_assert(expert.get("evidence_requirement") == "INTERNAL_KNOWLEDGE", f"software evidence policy mismatch: {expert}")
_assert(expert.get("requires_verification") is True, "software recommendation must require verification")
_assert(expert.get("requires_research") is False, "non-current software comparison should not force research")
_assert(expert.get("answer_boundary") == "VERIFY", f"software boundary should be VERIFY: {expert}")
_assert("matched_signals" not in expert, "public expert metadata must not expose internal classifier signals")
_assert(software.get("hidden_reasoning_exposed") is False, "hidden reasoning must remain private")
print("live software expert metadata: PASS")


current = _chat("What is the current market price and latest news for this investment?")
_assert(current.get("status") == "FAILED", "current-market request without research provider must fail safely")
current_expert = ((current.get("cognitive") or {}).get("expert") or {})
_assert(current_expert.get("requires_research") is True, "current-market expert policy must require research")
_assert(current_expert.get("evidence_requirement") == "EXTERNAL_CURRENT", f"current evidence policy mismatch: {current_expert}")
_assert(current_expert.get("answer_boundary") == "RESEARCH_REQUIRED", f"current request must remain research-required: {current_expert}")
_assert(float(current_expert.get("confidence_ceiling", 1.0)) <= 0.62, "missing current evidence must cap confidence")
print("live current-data expert boundary: PASS")


equation = _chat("Solve 2x - 4 + 4 = 9")
_assert(equation.get("status") == "RESPOND", "deterministic equation path must remain available")
_assert("x = 4.5" in str(equation.get("message", "")).lower(), "v0.19 deterministic equation behavior must be preserved")
equation_expert = ((equation.get("cognitive") or {}).get("expert") or {})
_assert(equation_expert.get("domain") == "GENERAL", "plain algebra should remain general expert domain")
print("v0.19 deterministic behavior preserved under v0.20: PASS")


capabilities = httpx.get(f"{BASE_URL}/testing/knowledge/capabilities", timeout=TIMEOUT)
_assert(capabilities.status_code == 200, "Checkpoint 2 requires live knowledge test hooks")
_assert((capabilities.json() or {}).get("database_backend") == "postgresql", "Checkpoint 2 must use PostgreSQL knowledge")
print("v0.20 expert knowledge backend: PASS")


def _knowledge_post(path: str, payload: dict) -> dict:
    response = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=TIMEOUT)
    _assert(response.status_code == 200, f"{path} expected 200, got {response.status_code}: {response.text}")
    return response.json() if response.content else {}


def _scoped_chat(message: str, scope: dict) -> dict:
    payload = {"message": message}
    payload.update(scope)
    return _knowledge_post("/chat", payload)


_knowledge_post("/testing/knowledge/reset", {})
conflict_scope = {
    "workspace_id": "v020-expert-conflict-ws",
    "business_id": "v020-expert-conflict-biz",
    "user_id": "v020-expert-conflict-user",
}
for source_id, content in (
    ("doc:atlas:db:postgres", "Project Atlas database architecture uses PostgreSQL."),
    ("doc:atlas:db:mysql", "Project Atlas database architecture uses MySQL."),
):
    payload = {
        **conflict_scope,
        "source_type": "DOCUMENT",
        "source_id": source_id,
        "source_title": source_id,
        "subject": "project.atlas.database.architecture",
        "content": content,
        "authority": "AUTHORITATIVE",
        "confidence": 0.92,
    }
    ingest = _knowledge_post("/testing/knowledge/ingest", payload)
    _assert(ingest.get("accepted") is True, f"conflict knowledge ingest failed: {ingest}")

conflict = _scoped_chat(
    "Evaluate whether Project Atlas should keep its current database architecture.",
    conflict_scope,
)
_assert(conflict.get("status") == "RESPOND", f"conflict request must produce bounded response: {conflict}")
conflict_message = str(conflict.get("message", "")).lower()
_assert("conflicting authorized project atlas knowledge" in conflict_message, f"conflict must be explicit: {conflict_message}")
_assert("keep a consistency-first architecture" not in conflict_message, "conflicting evidence must not produce a definitive architecture recommendation")
conflict_cognitive = conflict.get("cognitive") or {}
conflict_expert = conflict_cognitive.get("expert") or {}
_assert(conflict_expert.get("domain") == "SOFTWARE_ENGINEERING", f"database architecture should select software expert: {conflict_expert}")
_assert(conflict_expert.get("answer_boundary") == "CLARIFICATION_REQUIRED", f"conflict must require clarification: {conflict_expert}")
_assert(float(conflict_expert.get("confidence_ceiling", 1.0)) <= 0.45, "conflicting knowledge must sharply cap expert confidence")
_assert(conflict_cognitive.get("knowledge_boundary") == "CONFLICTING_KNOWLEDGE", f"runtime knowledge boundary mismatch: {conflict_cognitive}")
print("live expert conflict boundary: PASS")


_knowledge_post("/testing/knowledge/reset", {})
missing_scope = {
    "workspace_id": "v020-expert-missing-ws",
    "business_id": "v020-expert-missing-biz",
    "user_id": "v020-expert-missing-user",
}
missing = _scoped_chat(
    "Evaluate whether Project Atlas should keep its current database architecture.",
    missing_scope,
)
_assert(missing.get("status") == "RESPOND", f"missing-data request must respond safely: {missing}")
missing_message = str(missing.get("message", "")).lower()
_assert("additional project data is required" in missing_message, f"missing knowledge must be explicit: {missing_message}")
missing_cognitive = missing.get("cognitive") or {}
missing_expert = missing_cognitive.get("expert") or {}
_assert(missing_expert.get("domain") == "SOFTWARE_ENGINEERING", f"missing architecture request should remain software expert: {missing_expert}")
_assert(missing_expert.get("answer_boundary") == "DATA_REQUIRED", f"missing knowledge must stay DATA_REQUIRED: {missing_expert}")
_assert(float(missing_expert.get("confidence_ceiling", 1.0)) <= 0.55, "missing knowledge must cap expert confidence")
_assert(missing_cognitive.get("knowledge_record_count") == 0, "missing-data expert answer must not invent knowledge records")
print("live expert missing-knowledge boundary: PASS")


_knowledge_post("/testing/knowledge/reset", {})
grounded_scope = {
    "workspace_id": "v020-expert-grounded-ws",
    "business_id": "v020-expert-grounded-biz",
    "user_id": "v020-expert-grounded-user",
}
for payload in (
    {
        **grounded_scope,
        "source_type": "DATABASE",
        "source_id": "db:atlas:primary",
        "source_title": "Atlas runtime configuration",
        "subject": "project.atlas.database",
        "content": "Project Atlas currently uses PostgreSQL.",
        "authority": "PRIMARY",
        "confidence": 0.97,
    },
    {
        **grounded_scope,
        "source_type": "DOCUMENT",
        "source_id": "doc:atlas:consistency",
        "source_title": "Atlas consistency requirement",
        "subject": "project.atlas.consistency",
        "content": "Project Atlas requires strict transactional consistency.",
        "authority": "AUTHORITATIVE",
        "confidence": 0.95,
    },
):
    ingest = _knowledge_post("/testing/knowledge/ingest", payload)
    _assert(ingest.get("accepted") is True, f"grounded knowledge ingest failed: {ingest}")

grounded = _scoped_chat(
    "Evaluate whether Project Atlas should keep its current database architecture.",
    grounded_scope,
)
_assert(grounded.get("status") == "RESPOND", f"grounded expert request must respond: {grounded}")
grounded_message = str(grounded.get("message", "")).lower()
_assert("retrieved knowledge indicates" in grounded_message, f"grounded answer must identify retrieved evidence: {grounded_message}")
grounded_cognitive = grounded.get("cognitive") or {}
grounded_expert = grounded_cognitive.get("expert") or {}
_assert(grounded_expert.get("domain") == "SOFTWARE_ENGINEERING", f"grounded architecture request should select software expert: {grounded_expert}")
_assert(grounded_expert.get("answer_boundary") == "VERIFY", f"grounded expert answer should remain verification-bounded: {grounded_expert}")
_assert(int(grounded_cognitive.get("knowledge_record_count", 0)) >= 1, "grounded expert answer must report real knowledge records")
_assert(grounded_cognitive.get("grounding_status") in {"GROUNDED", "PARTIALLY_GROUNDED"}, f"grounding status must be explicit: {grounded_cognitive}")
print("live expert grounded-knowledge boundary: PASS")


print("SHY v0.20 EXPERT INTELLIGENCE CHECKPOINT 2: PASS")
