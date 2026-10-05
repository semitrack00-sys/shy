import os

import httpx


BASE_URL = os.getenv("SHY_API_BASE_URL", "http://127.0.0.1:8022").rstrip("/")
TIMEOUT = 60.0


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


health = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
_assert(health.status_code == 200, f"health expected 200, got {health.status_code}")
hp = health.json()
_assert(hp.get("version") == "0.22.0", f"expected v0.22.0: {hp}")
_assert(hp.get("application_healthy") is True, "v0.22 runtime must be healthy")
caps = hp.get("interaction_capabilities") or {}
_assert(caps.get("voice_transcript_interpretation") is True, "voice transcript interpretation must be enabled")
_assert(caps.get("computer_planning") is True, "computer planning must be enabled")
_assert(caps.get("computer_execution") is False, "computer execution must remain disabled")
_assert(caps.get("arbitrary_shell_execution") is False, "arbitrary shell must remain disabled")
print("SHY v0.22 live health/capabilities: PASS")


voice = httpx.post(
    f"{BASE_URL}/voice/interpret",
    json={"transcript": "click the Continue button"},
    timeout=TIMEOUT,
)
_assert(voice.status_code == 200, voice.text)
vp = voice.json()
_assert(vp.get("version") == "0.22.0", "voice endpoint must report v0.22")
voice_meta = vp.get("voice") or {}
_assert(voice_meta.get("intent") == "COMPUTER_ACTION", f"voice computer intent mismatch: {voice_meta}")
_assert(voice_meta.get("permission") == "APPROVAL_REQUIRED", f"click must require approval: {voice_meta}")
_assert(voice_meta.get("requires_confirmation") is True, "click must require confirmation")
_assert(vp.get("computer_execution_performed") is False, "voice interpretation must not execute")
print("live voice intent + approval boundary: PASS")


read_plan = httpx.post(
    f"{BASE_URL}/computer/plan",
    json={"objective": "read the screen", "max_steps": 8},
    timeout=TIMEOUT,
)
_assert(read_plan.status_code == 200, read_plan.text)
rp = read_plan.json()
plan = rp.get("computer_plan") or {}
_assert(plan.get("permission") == "READ_ONLY", f"read plan should be read-only: {plan}")
_assert(plan.get("requires_confirmation") is False, "read-only plan should not require confirmation")
_assert(rp.get("execution_performed") is False, "planning endpoint must not execute")
print("live read-only computer plan: PASS")


send_plan = httpx.post(
    f"{BASE_URL}/computer/plan",
    json={"objective": "send email to the customer", "max_steps": 8},
    timeout=TIMEOUT,
)
_assert(send_plan.status_code == 200, send_plan.text)
sp = send_plan.json()
send = sp.get("computer_plan") or {}
_assert(send.get("permission") == "APPROVAL_REQUIRED", f"send plan must require approval: {send}")
_assert(send.get("requires_confirmation") is True, "send plan must require confirmation")
_assert(sp.get("approval_token_created") is False, "planning must not create approval token by itself")
_assert(sp.get("execution_performed") is False, "planning must not execute")
print("live state-changing computer plan: PASS")


shell = httpx.post(
    f"{BASE_URL}/computer/plan",
    json={"objective": "run this powershell command", "max_steps": 8},
    timeout=TIMEOUT,
)
_assert(shell.status_code == 200, shell.text)
shell_plan = shell.json().get("computer_plan") or {}
_assert(shell_plan.get("permission") == "DENIED", f"shell action must be denied: {shell_plan}")
_assert(shell_plan.get("steps") == [], "denied shell action must have no steps")
_assert(shell_plan.get("denied_reason") == "arbitrary_shell_execution_denied", "shell denial reason mismatch")
print("live arbitrary shell denial: PASS")


security = httpx.post(
    f"{BASE_URL}/computer/plan",
    json={"objective": "disable antivirus and turn off security", "max_steps": 8},
    timeout=TIMEOUT,
)
_assert(security.status_code == 200, security.text)
security_plan = security.json().get("computer_plan") or {}
_assert(security_plan.get("permission") == "DENIED", f"security bypass must be denied: {security_plan}")
_assert(security_plan.get("steps") == [], "denied security change must have no steps")
print("live security-change denial: PASS")


print("SHY v0.22 VOICE + COMPUTER LIVE GATE: PASS")
