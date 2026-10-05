from datetime import datetime, timedelta, timezone
import os

import httpx


BASE_URL = os.getenv("SHY_API_BASE_URL", "http://127.0.0.1:8019").rstrip("/")
TIMEOUT = 60.0


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _post_chat(message: str, **extra) -> dict:
    payload = {
        "message": message,
        "workspace_id": "v019-user-basics-ws",
        "business_id": "v019-user-basics-biz",
        "user_id": "v019-user-basics-user",
    }
    payload.update(extra)
    response = httpx.post(f"{BASE_URL}/chat", json=payload, timeout=TIMEOUT)
    _assert(response.status_code == 200, f"chat expected 200, got {response.status_code}: {response.text}")
    result = response.json()
    _assert(result.get("status") == "RESPOND", f"chat must RESPOND, got {result.get('status')}")
    return result


def main():
    health = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
    _assert(health.status_code == 200, f"health expected 200, got {health.status_code}")
    health_payload = health.json()
    _assert(health_payload.get("version") == "0.19.0", "live runtime must be SHY v0.19.0")
    _assert(bool(health_payload.get("application_healthy")), "live runtime must be healthy")

    capability = _post_chat("what you van do")
    capability_text = str(capability.get("message", ""))
    capability_lower = capability_text.lower()
    _assert("durable" in capability_lower, "capabilities should mention durable memory/knowledge")
    _assert("postgresql" in capability_lower, "capabilities should mention PostgreSQL-backed knowledge")
    _assert("multi-step" in capability_lower, "capabilities should mention bounded multi-step work")
    _assert("beta logistics" not in capability_lower, "capabilities must not invent the Beta Logistics ecosystem")
    _assert(capability.get("provider") == "shy-core", "capability answer should come from deterministic SHY core")
    print("SHY capability truthfulness: PASS")

    offset_minutes = -420
    tz = timezone(timedelta(minutes=offset_minutes))
    before = datetime.now(timezone.utc).astimezone(tz)
    date_result = _post_chat(
        "whats day is to day",
        client_utc_offset_minutes=offset_minutes,
        client_timezone="America/Los_Angeles",
    )
    after = datetime.now(timezone.utc).astimezone(tz)
    accepted_dates = {
        f"{value.strftime('%A, %B')} {value.day}, {value.year}"
        for value in (before, after)
    }
    date_text = str(date_result.get("message", ""))
    _assert(any(expected in date_text for expected in accepted_dates), f"date response did not match local date: {date_text}")
    _assert("don't have access to real-time" not in date_text.lower(), "SHY must not deny access to the clock context supplied by the client")
    _assert(date_result.get("provider") == "shy-core", "date answer should come from deterministic SHY core")
    print("SHY local-date response: PASS")

    time_result = _post_chat(
        "what time is it",
        client_utc_offset_minutes=offset_minutes,
        client_timezone="America/Los_Angeles",
    )
    time_text = str(time_result.get("message", ""))
    _assert("America/Los_Angeles" in time_text, "time response should identify the client timezone")
    _assert("current time" in time_text.lower(), "time response should clearly state the current time")
    print("SHY local-time response: PASS")

    print("SHY v0.19 USER BASICS GATE 5: PASS")


if __name__ == "__main__":
    main()
