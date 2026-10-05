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


print("SHY v0.20 EXPERT INTELLIGENCE LIVE CHECKPOINT 1: PASS")
