import os

import httpx


WEB_BASE_URL = os.getenv("SHY_WEB_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
EXPECTED_VERSION = os.getenv("SHY_EXPECTED_VERSION", "0.20.0")
TIMEOUT = 120.0


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _post(message: str) -> dict:
    response = httpx.post(
        f"{WEB_BASE_URL}/api/shy/agent",
        json={
            "message": message,
            "workspace_id": "v020-web-expert-ws",
            "business_id": "v020-web-expert-biz",
            "user_id": "v020-web-expert-user",
        },
        timeout=TIMEOUT,
    )
    _assert(response.status_code == 200, f"web expert proxy expected 200, got {response.status_code}: {response.text}")
    return response.json()


def main():
    health = httpx.get(f"{WEB_BASE_URL}/api/shy/health", timeout=TIMEOUT)
    _assert(health.status_code == 200, f"web health expected 200, got {health.status_code}")
    health_payload = health.json()
    _assert(health_payload.get("version") == EXPECTED_VERSION, f"web must expose SHY {EXPECTED_VERSION}")
    _assert(health_payload.get("application_healthy") is True, "web must expose healthy v0.20 runtime")
    print("v0.20 web expert health: PASS")

    software = _post(
        "Compare PostgreSQL and MySQL for a software architecture and recommend the safer tradeoffs."
    )
    _assert(software.get("status") == "RESPOND", f"software web request must respond: {software}")
    expert = ((software.get("cognitive") or {}).get("expert") or {})
    frame = expert.get("response_frame") or {}
    _assert(expert.get("domain") == "SOFTWARE_ENGINEERING", f"web software domain mismatch: {expert}")
    _assert(expert.get("playbook_id") == "software-engineering-v1", f"web playbook id mismatch: {expert}")
    _assert(frame.get("decision") == "VERIFY", f"web software decision must be VERIFY: {frame}")
    _assert(expert.get("requires_verification") is True, "web software expert must require verification")
    _assert(software.get("hidden_reasoning_exposed") is False, "web path must not expose hidden reasoning")
    print("v0.20 web software expert metadata: PASS")

    high_stakes = _post("Should I buy this stock today for my retirement portfolio?")
    _assert(high_stakes.get("status") == "FAILED", f"high-stakes web request must fail safely: {high_stakes}")
    high_expert = ((high_stakes.get("cognitive") or {}).get("expert") or {})
    high_frame = high_expert.get("response_frame") or {}
    _assert(high_expert.get("risk_level") == "HIGH", f"web high-stakes risk mismatch: {high_expert}")
    _assert(high_expert.get("answer_boundary") == "AUTHORITATIVE_EVIDENCE_REQUIRED", f"web authority boundary mismatch: {high_expert}")
    _assert(high_frame.get("authoritative_sources_sufficient") is False, f"web authority sufficiency mismatch: {high_frame}")
    _assert(high_frame.get("next_evidence_needed") == ["authoritative_source"], f"web next evidence mismatch: {high_frame}")
    _assert(high_stakes.get("research_invoked") is True, "web high-stakes request must invoke research path")
    print("v0.20 web high-stakes authority boundary: PASS")

    equation = _post("Solve 2x - 4 + 4 = 9")
    _assert(equation.get("status") == "RESPOND", "web deterministic equation must still respond")
    _assert("x = 4.5" in str(equation.get("message", "")).lower(), "web deterministic equation must remain correct")
    print("v0.20 web v0.19 behavior preservation: PASS")

    print("SHY v0.20 WEB EXPERT RELEASE PATH: PASS")


if __name__ == "__main__":
    main()
