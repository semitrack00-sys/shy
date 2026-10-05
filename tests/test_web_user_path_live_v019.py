from datetime import datetime, timedelta, timezone
import os

import httpx


WEB_BASE_URL = os.getenv("SHY_WEB_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
EXPECTED_VERSION = os.getenv("SHY_EXPECTED_VERSION", "0.19.0")
TIMEOUT = 120.0


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _web_chat(message: str, **extra) -> dict:
    payload = {"message": message}
    payload.update(extra)
    response = httpx.post(f"{WEB_BASE_URL}/api/shy/agent", json=payload, timeout=TIMEOUT)
    _assert(response.status_code == 200, f"web assistant proxy expected 200, got {response.status_code}: {response.text}")
    result = response.json()
    _assert(result.get("status") == "RESPOND", f"web assistant proxy must RESPOND, got {result.get('status')}")
    return result


def main():
    health = httpx.get(f"{WEB_BASE_URL}/api/shy/health", timeout=TIMEOUT)
    _assert(health.status_code == 200, f"web health proxy expected 200, got {health.status_code}: {health.text}")
    health_payload = health.json()
    _assert(health_payload.get("version") == EXPECTED_VERSION, f"web health proxy must expose {EXPECTED_VERSION}")
    _assert(health_payload.get("application_healthy") is True, "web health proxy must expose truthful healthy state")
    _assert(health_payload.get("ollama_connected") is True, "web health proxy must expose Ollama state")
    _assert(health_payload.get("local_model_available") is True, "web health proxy must expose configured model state")
    print("web health proxy v0.19 integrity: PASS")

    capabilities = _web_chat("what you van do")
    capability_text = str(capabilities.get("message", "")).lower()
    _assert("postgresql" in capability_text and "durable" in capability_text, "web path must use v0.19 SHY capability response")
    _assert("beta logistics" not in capability_text, "web path must not hallucinate Beta Logistics")
    _assert(capabilities.get("provider") == "shy-core", "web path must reach modern /chat deterministic core")
    print("web capability path: PASS")

    offset_minutes = -420
    tz = timezone(timedelta(minutes=offset_minutes))
    before = datetime.now(timezone.utc).astimezone(tz)
    date_payload = _web_chat(
        "whats day is to day",
        client_utc_offset_minutes=offset_minutes,
        client_timezone="America/Los_Angeles",
    )
    after = datetime.now(timezone.utc).astimezone(tz)
    date_text = str(date_payload.get("message", ""))
    accepted_dates = {
        f"{value.strftime('%A, %B')} {value.day}, {value.year}"
        for value in (before, after)
    }
    _assert(any(expected in date_text for expected in accepted_dates), f"web date response did not match browser offset: {date_text}")
    print("web local-date path: PASS")

    delivery_prompt = """I run a delivery company with 100 deliveries per week.

18 deliveries are late:
- 9 because of loading delays
- 4 because of traffic
- 3 because of driver scheduling
- 2 because of mechanical problems

A new loading system would reduce loading-related delays by 50%.
It costs $2,000 per month.

Each prevented late delivery saves about $120.

Analyze whether I should buy the new loading system."""
    delivery = _web_chat(delivery_prompt)
    delivery_text = str(delivery.get("message", "")).lower()
    for fragment in (
        "current late-delivery rate: 18%",
        "expected prevented late deliveries: 4.5 per week",
        "expected weekly savings: $540",
        "expected monthly savings (4-week assumption): $2,160",
        "net monthly benefit after $2,000 cost: $160",
        "slightly financially positive",
    ):
        _assert(fragment in delivery_text, f"web delivery response missing: {fragment}")
    _assert(delivery.get("execution_mode") == "MULTI_STEP", "web delivery request must reach v0.19 multi-step chat path")
    print("web delivery investment path: PASS")

    equation = _web_chat("Solve 2x - 4 + 4 = 9")
    equation_text = str(equation.get("message", "")).lower()
    _assert("x = 4.5" in equation_text, "web equation response must be x = 4.5")
    _assert("solution is 5" not in equation_text, "web equation response must not contradict itself")
    print("web equation consistency path: PASS")

    post_health = httpx.get(f"{WEB_BASE_URL}/api/shy/health", timeout=TIMEOUT)
    _assert(post_health.status_code == 200, "post-request web health proxy must remain available")
    post_health_payload = post_health.json()
    routing = post_health_payload.get("model_routing") or {}
    _assert(int(routing.get("selection_failures", -1)) == 0, f"successful user requests must not create routing selection failures: {routing}")
    _assert(int(routing.get("execution_failures", -1)) == 0, f"successful user requests must not create routing execution failures: {routing}")
    _assert(routing.get("degraded") is False, f"successful user requests must leave model routing healthy: {routing}")
    print("web routing diagnostics remain clean: PASS")

    print("SHY v0.19 WEB USER PATH GATE: PASS")


if __name__ == "__main__":
    main()
