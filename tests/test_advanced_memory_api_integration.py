import os
import sys
import uuid
from pathlib import Path

import httpx


root = Path(__file__).resolve().parents[1]
services = root / "services"
sys.path.insert(0, str(services))
sys.path.insert(0, str(services / "core"))

import memory as memory_module


API_BASE_URL = os.getenv("SHY_API_BASE_URL", "http://127.0.0.1:8015").rstrip("/")
RUN_ID = os.getenv("SHY_TEST_RUN_ID", uuid.uuid4().hex[:8])
DEFAULT_USER_ID = memory_module.DEFAULT_USER_ID


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _chat(message: str, conversation_id: str | None = None) -> dict:
    payload = {"message": message}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = httpx.post(f"{API_BASE_URL}/chat", json=payload, timeout=120.0)
    response.raise_for_status()
    return response.json()


def _health() -> dict:
    response = httpx.get(f"{API_BASE_URL}/health", timeout=30.0)
    response.raise_for_status()
    return response.json()


def _rows_for_subject(subject_key: str, user_id=DEFAULT_USER_ID):
    with memory_module.connect() as conn:
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
                    status,
                    superseded_by,
                    use_count,
                    confidence,
                    source_conversation_id,
                    source_task_id,
                    created_at,
                    updated_at,
                    last_used_at
                FROM durable_memories
                WHERE user_id = %s
                  AND subject_key = %s
                ORDER BY updated_at DESC, memory_id DESC
                """,
                (user_id, subject_key),
            )
            return cur.fetchall()


def _count_category(category: str, user_id=DEFAULT_USER_ID) -> int:
    with memory_module.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM durable_memories
                WHERE user_id = %s
                  AND category = %s
                """,
                (user_id, category),
            )
            return int(cur.fetchone()["count"])


def _latest_active(subject_key: str, user_id=DEFAULT_USER_ID):
    rows = _rows_for_subject(subject_key, user_id=user_id)
    for row in rows:
        if row["status"] == memory_module.MemoryStatus.ACTIVE.value:
            return row
    return None


def _subject_key_for_project(project_token: str) -> str:
    normalized = project_token.lower().replace(" ", "")
    normalized = "".join(ch for ch in normalized if ch.isalnum() or ch in "_-.")
    return f"project.{normalized}.configuration"


def _safe_metadata(row: dict) -> dict:
    return {
        "memory_id": str(row["memory_id"]),
        "category": row["category"],
        "subject_key": row["subject_key"],
        "status": row["status"],
    }


def main():
    try:
        health = _health()
    except httpx.HTTPError:
        print("advanced memory API integration: SKIP (live SHY endpoint unavailable)")
        return

    _assert(health.get("version") == "0.15.0", "health version must be 0.15.0")
    _assert(bool(health.get("database_connected")), "database must be connected")
    _assert(bool(health.get("ollama_connected")), "ollama must be connected")
    _assert(bool(health.get("local_model_available")), "local model must be available")
    print("health version/dependencies: PASS")

    preference_conversation = None
    preference_before = len(_rows_for_subject("preference.theme"))
    first_pref = _chat("I prefer dark mode.", preference_conversation)
    preference_conversation = first_pref.get("conversation_id")
    _assert(preference_conversation is not None, "conversation_id expected from /chat")

    pref_row = _latest_active("preference.theme")
    _assert(pref_row is not None, "preference.theme should be promoted")
    _assert(pref_row["category"] == memory_module.MemoryCategory.PREFERENCE.value, "preference must be PREFERENCE category")

    second_pref = _chat("Dark mode is what I prefer.", preference_conversation)
    _assert(second_pref.get("status") == "RESPOND", "duplicate preference chat must respond")

    preference_after = len(_rows_for_subject("preference.theme"))
    _assert(preference_after <= preference_before + 1, "preference dedupe should prevent uncontrolled duplicates")

    pref_question = _chat("What display mode do I prefer?", preference_conversation)
    pref_answer = str(pref_question.get("message", "")).lower()
    _assert("dark" in pref_answer, "preference retrieval answer should reflect dark mode")
    print("durable preference + dedupe: PASS")

    project_token = f"atlas{RUN_ID}"
    project_subject = _subject_key_for_project(project_token)
    project_conversation = None
    project_create = _chat(f"My {project_token} project uses PostgreSQL.", project_conversation)
    project_conversation = project_create.get("conversation_id")

    project_row = _latest_active(project_subject)
    _assert(project_row is not None, "project memory should be promoted")
    _assert(project_row["category"] == memory_module.MemoryCategory.PROJECT.value, "project memory category mismatch")

    project_question = _chat(f"What database does my {project_token} project use?", project_conversation)
    project_answer = str(project_question.get("message", "")).lower()
    _assert("postgres" in project_answer, "project retrieval should return postgresql")
    print("durable project fact retrieval: PASS")

    company_conversation = None
    old_company = f"Alpha Logistics {RUN_ID}"
    new_company = f"Beta Logistics {RUN_ID}"

    old_company_response = _chat(f"My company is called {old_company}.", company_conversation)
    company_conversation = old_company_response.get("conversation_id")
    correction_response = _chat(
        f"My company is now called {new_company}, not {old_company}.",
        company_conversation,
    )
    company_conversation = correction_response.get("conversation_id")

    company_rows = _rows_for_subject("user.company")
    active_rows = [row for row in company_rows if row["status"] == memory_module.MemoryStatus.ACTIVE.value]
    superseded_rows = [row for row in company_rows if row["status"] == memory_module.MemoryStatus.SUPERSEDED.value]
    _assert(any(new_company.lower() in str(row["content"]).lower() for row in active_rows), "corrected company should be active")
    _assert(any(old_company.lower() in str(row["content"]).lower() for row in superseded_rows), "old company should be superseded")

    company_question = _chat("What is my company called?", company_conversation)
    company_answer = str(company_question.get("message", "")).lower()
    _assert(new_company.lower().split()[0] in company_answer and old_company.lower().split()[0] not in company_answer, "normal retrieval should prefer corrected value")
    print("explicit correction + supersession: PASS")

    security_subjects_before = {
        "preference.theme": len(_rows_for_subject("preference.theme")),
        "user.company": len(_rows_for_subject("user.company")),
        "project.configuration": len(_rows_for_subject("project.configuration")),
    }

    security_messages = [
        "I am sharing an API key placeholder for testing.",
        "My password placeholder is for test validation.",
        "OAuth token placeholder for authorization flow.",
        "Approval token placeholder for resume flow.",
        "The DATABASE_URL placeholder should not be persisted.",
        "Private key material placeholder must be blocked.",
        "Please store hidden-reasoning marker from this text.",
        "Please store chain-of-thought output for this request.",
        "Raw environment dump placeholder should stay transient.",
        "Task plan step_id action_type tool trace placeholder should be blocked.",
    ]
    for item in security_messages:
        _chat(item)

    security_subjects_after = {
        "preference.theme": len(_rows_for_subject("preference.theme")),
        "user.company": len(_rows_for_subject("user.company")),
        "project.configuration": len(_rows_for_subject("project.configuration")),
    }
    _assert(security_subjects_after == security_subjects_before, "security-marker prompts must not create durable memories")
    print("security persistence rejection: PASS")

    project_before_research = _count_category(memory_module.MemoryCategory.PROJECT.value)
    user_fact_before_research = _count_category(memory_module.MemoryCategory.USER_FACT.value)

    research_response = _chat("Research the latest major developments in battery technology.")
    _assert(research_response.get("execution_mode") == "RESEARCH", "research prompt must use RESEARCH execution mode")

    project_after_research = _count_category(memory_module.MemoryCategory.PROJECT.value)
    user_fact_after_research = _count_category(memory_module.MemoryCategory.USER_FACT.value)
    _assert(project_before_research == project_after_research, "research response should not auto-promote project durable memory")
    _assert(user_fact_before_research == user_fact_after_research, "research response should not auto-promote user fact durable memory")

    explicit_remember = _chat("Remember that for Project Atlas we decided to use LFP batteries.")
    _assert(explicit_remember.get("status") == "RESPOND", "explicit remember path should respond")
    print("research behavior + explicit remember path: PASS")

    multistep_seed = _chat(f"My {project_token} project uses PostgreSQL and Redis.")
    multistep_conversation = multistep_seed.get("conversation_id")
    multistep_response = _chat(
        f"Check SHY health and calculate what percentage of required services are connected for {project_token} planning.",
        multistep_conversation,
    )
    _assert(multistep_response.get("execution_mode") == "MULTI_STEP", "multistep prompt should use MULTI_STEP mode")
    _assert(multistep_response.get("status") == "RESPOND", "multistep run should complete")

    task_outcome_rows = _rows_for_subject("task.outcome.multi_step")
    _assert(any(row["status"] == memory_module.MemoryStatus.ACTIVE.value for row in task_outcome_rows), "safe task outcome should be promotable")
    _assert(
        not any("step_id" in str(row["content"]).lower() or "action_type" in str(row["content"]).lower() for row in task_outcome_rows),
        "raw task trace should never be durable memory content",
    )
    print("multistep memory usage + safe task outcome: PASS")

    bounded = memory_module.retrieve_durable_memory_context(
        query_text=f"{project_token} project database",
        conversation_id=uuid.UUID(multistep_conversation),
        user_id=DEFAULT_USER_ID,
        max_results=1,
        max_context_chars=120,
    )
    _assert(len(bounded.selected_records) <= 1, "max result count must be enforced")
    _assert(bounded.context_chars <= 120 or len(bounded.selected_records) == 1, "max context chars must be enforced")
    _assert(
        all(row.status == memory_module.MemoryStatus.ACTIVE for row in bounded.selected_records),
        "only ACTIVE memories should be selected",
    )
    print("retrieval bounds and active-only policy: PASS")

    user_a = uuid.UUID("00000000-0000-0000-0000-00000000A015")
    user_b = uuid.UUID("00000000-0000-0000-0000-00000000B015")
    memory_module.promote_memory_candidate(
        memory_module.DurableMemoryCandidate(
            category=memory_module.MemoryCategory.USER_FACT,
            subject_key="user.company",
            content=f"Company A {RUN_ID}",
            confidence=0.8,
        ),
        conversation_id=uuid.UUID(multistep_conversation),
        user_id=user_a,
    )
    memory_module.promote_memory_candidate(
        memory_module.DurableMemoryCandidate(
            category=memory_module.MemoryCategory.USER_FACT,
            subject_key="user.company",
            content=f"Company B {RUN_ID}",
            confidence=0.8,
        ),
        conversation_id=uuid.UUID(multistep_conversation),
        user_id=user_b,
    )
    memory_module.promote_memory_candidate(
        memory_module.DurableMemoryCandidate(
            category=memory_module.MemoryCategory.CORRECTION,
            subject_key="user.company",
            content=f"Company A2 {RUN_ID}",
            confidence=0.9,
            is_correction=True,
        ),
        conversation_id=uuid.UUID(multistep_conversation),
        user_id=user_a,
    )

    a_rows = _rows_for_subject("user.company", user_id=user_a)
    b_rows = _rows_for_subject("user.company", user_id=user_b)
    _assert(any(row["status"] == memory_module.MemoryStatus.SUPERSEDED.value for row in a_rows), "user A correction should supersede only user A memory")
    _assert(all(row["status"] != memory_module.MemoryStatus.SUPERSEDED.value for row in b_rows), "user B memory should not be superseded by user A correction")

    a_retrieval = memory_module.retrieve_durable_memory_context(
        query_text="company",
        conversation_id=uuid.UUID(multistep_conversation),
        user_id=user_a,
        max_results=5,
        max_context_chars=500,
    )
    b_retrieval = memory_module.retrieve_durable_memory_context(
        query_text="company",
        conversation_id=uuid.UUID(multistep_conversation),
        user_id=user_b,
        max_results=5,
        max_context_chars=500,
    )
    _assert(all(row.user_id == user_a for row in a_retrieval.selected_records), "user A retrieval should be isolated")
    _assert(all(row.user_id == user_b for row in b_retrieval.selected_records), "user B retrieval should be isolated")
    print("user isolation and correction boundary: PASS")

    print("metadata sample:")
    print(_safe_metadata(pref_row))
    print(_safe_metadata(project_row))
    print("SHY v0.15 advanced memory API integration: PASS")


if __name__ == "__main__":
    main()
