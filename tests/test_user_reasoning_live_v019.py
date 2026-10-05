import os

import httpx


BASE_URL = os.getenv("SHY_API_BASE_URL", "http://127.0.0.1:8019").rstrip("/")
TIMEOUT = 240.0


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def main():
    health = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    _assert(health.status_code == 200, f"health expected 200, got {health.status_code}")
    health_payload = health.json()
    _assert(health_payload.get("version") == "0.19.0", "live runtime must be SHY v0.19.0")
    _assert(bool(health_payload.get("application_healthy")), "application must be healthy")
    _assert(bool(health_payload.get("database_connected")), "database must be connected")
    _assert(bool(health_payload.get("local_model_available")), "local model must be available")

    prompt = """I run a delivery company with 100 deliveries per week.

18 deliveries are late:
- 9 because of loading delays
- 4 because of traffic
- 3 because of driver scheduling
- 2 because of mechanical problems

A new loading system would reduce loading-related delays by 50%.
It costs $2,000 per month.

Each prevented late delivery saves about $120.

Analyze whether I should buy the new loading system.

Show:
1. Current late-delivery rate
2. Expected prevented late deliveries
3. Weekly savings
4. Monthly savings
5. Net monthly benefit after the $2,000 cost
6. Whether the investment makes financial sense
7. Assumptions
8. Confidence level
9. Strongest remaining cause of late deliveries"""

    response = httpx.post(
        f"{BASE_URL}/chat",
        json={
            "message": prompt,
            "workspace_id": "v019-user-reasoning-ws",
            "business_id": "v019-user-reasoning-biz",
            "user_id": "v019-user-reasoning-user",
        },
        timeout=TIMEOUT,
    )
    _assert(response.status_code == 200, f"chat expected 200, got {response.status_code}: {response.text}")
    payload = response.json()
    _assert(payload.get("status") == "RESPOND", f"chat must RESPOND, got {payload.get('status')}")
    _assert(payload.get("execution_mode") == "MULTI_STEP", "delivery investment analysis should use bounded multi-step business workflow")
    text = str(payload.get("message", ""))

    expected_fragments = (
        "Current late-delivery rate: 18%",
        "Expected prevented late deliveries: 4.5 per week",
        "Expected weekly savings: $540",
        "Expected monthly savings (4-week assumption): $2,160",
        "Net monthly benefit after $2,000 cost: $160",
        "slightly financially positive",
        "Strongest remaining cause after the change: loading delays at 4.5 expected late deliveries/week.",
    )
    for fragment in expected_fragments:
        _assert(fragment.lower() in text.lower(), f"missing expected output: {fragment}")

    _assert("temporarily unavailable" not in text.lower(), "user-facing failure text must not appear")
    _assert(payload.get("completion_criteria_met") is True, "multi-step task must satisfy completion criteria")

    business_audit = payload.get("business_audit") or {}
    _assert(business_audit.get("workflow_type") == "logistics_analysis", "business audit must identify logistics workflow")

    print("SHY v0.19 user-facing delivery investment reasoning: PASS")


if __name__ == "__main__":
    main()
