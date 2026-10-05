import os

import httpx


BASE_URL = os.getenv("SHY_API_BASE_URL", "http://127.0.0.1:8021").rstrip("/")
TIMEOUT = 90.0


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _post(path: str, payload: dict) -> dict:
    response = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=TIMEOUT)
    _assert(response.status_code == 200, f"{path} expected 200, got {response.status_code}: {response.text}")
    return response.json()


health = httpx.get(f"{BASE_URL}/health", timeout=TIMEOUT)
_assert(health.status_code == 200, f"health expected 200, got {health.status_code}")
health_payload = health.json()
_assert(health_payload.get("version") == "0.21.0", f"live runtime must be SHY v0.21.0: {health_payload}")
_assert(health_payload.get("application_healthy") is True, "v0.21 runtime must be healthy")
print("SHY v0.21 live health: PASS")


criteria = [
    {"name": "reliability", "weight": 0.45, "direction": "BENEFIT", "required": True},
    {"name": "cost", "weight": 0.25, "direction": "COST", "required": True},
    {"name": "evidence", "weight": 0.30, "direction": "BENEFIT", "required": True},
]
options = [
    {
        "name": "Option A",
        "metrics": {"reliability": 0.88, "cost": 0.55, "evidence": 0.80},
        "evidence_quality": 0.84,
    },
    {
        "name": "Option B",
        "metrics": {"reliability": 0.94, "cost": 0.35, "evidence": 0.92},
        "evidence_quality": 0.94,
    },
]

analysis = _post(
    "/decision/analyze",
    {
        "criteria": criteria,
        "options": options,
        "evidence_quality": 0.92,
    },
)
_assert(analysis.get("status") == "ok", f"decision analysis failed: {analysis}")
_assert(analysis.get("version") == "0.21.0", "decision API must report v0.21")
decision = analysis.get("decision") or {}
_assert(decision.get("selected_option") == "Option B", f"expected Option B, got {decision}")
_assert(decision.get("boundary") in {"RECOMMEND", "CONDITIONAL"}, f"unexpected decision boundary: {decision}")
_assert(analysis.get("learning_applied") is False, "decision analysis must not mutate learning")
_assert(analysis.get("hidden_reasoning_exposed") is False, "decision API must not expose hidden reasoning")
print("live structured decision analysis: PASS")


simulation = _post(
    "/decision/simulate",
    {
        "criteria": criteria,
        "options": options,
        "scenarios": [
            {
                "name": "normal",
                "probability": 0.6,
                "option_metric_deltas": {"Option A": {}, "Option B": {}},
            },
            {
                "name": "cost pressure",
                "probability": 0.4,
                "option_metric_deltas": {
                    "Option A": {"cost": 0.10},
                    "Option B": {"cost": 0.20},
                },
            },
        ],
        "max_scenarios": 12,
    },
)
sim = simulation.get("simulation") or {}
_assert(sim.get("selected_strategy") == "Option B", f"expected Option B in simulation, got {sim}")
_assert(len(sim.get("ranked") or []) == 2, "simulation should rank both options")
_assert(simulation.get("learning_applied") is False, "simulation must not mutate learning")
print("live bounded decision simulation: PASS")


unverified = _post(
    "/learning/evaluate",
    {
        "decision_id": "live-decision-001",
        "strategy_name": "Option B",
        "target_criterion": "reliability",
        "predicted_score": 0.80,
        "observed_score": 0.95,
        "verification": "UNVERIFIED",
        "evidence_ids": ["event-1"],
    },
)
unverified_learning = unverified.get("learning") or {}
_assert(unverified_learning.get("accepted") is False, "unverified outcome must not be accepted for learning")
_assert(unverified.get("persistent_change_applied") is False, "learning evaluation must not persist changes")
print("live unverified learning rejection: PASS")


verified = _post(
    "/learning/evaluate",
    {
        "decision_id": "live-decision-002",
        "strategy_name": "Option B",
        "target_criterion": "reliability",
        "predicted_score": 0.75,
        "observed_score": 0.95,
        "verification": "VERIFIED",
        "evidence_ids": ["verified-event-1"],
    },
)
verified_learning = verified.get("learning") or {}
_assert(verified_learning.get("accepted") is True, f"verified outcome should be learnable: {verified_learning}")
_assert(float(verified_learning.get("delta", 0.0)) > 0.0, "verified positive outcome should produce positive bounded delta")
_assert(verified.get("persistent_change_applied") is False, "Checkpoint 2 must remain non-persistent")
print("live verified learning evaluation: PASS")


protected = _post(
    "/learning/evaluate",
    {
        "decision_id": "live-decision-003",
        "strategy_name": "Option B",
        "target_criterion": "security policy",
        "predicted_score": 0.10,
        "observed_score": 1.00,
        "verification": "VERIFIED",
        "evidence_ids": ["verified-security-event"],
    },
)
protected_learning = protected.get("learning") or {}
_assert(protected_learning.get("accepted") is False, "security policy must remain protected from learning")
_assert(protected_learning.get("reason") == "protected_learning_target", f"protected reason mismatch: {protected_learning}")
print("live protected-policy learning rejection: PASS")


implicit_preview = _post(
    "/decision/feedback-preview",
    {
        "criteria": criteria,
        "explicit": False,
        "criterion_adjustments": {"reliability": 0.10},
        "note": "inferred from behavior",
    },
)
_assert(implicit_preview.get("applied_in_preview") is False, "implicit feedback must not change decision weights")
_assert(implicit_preview.get("persistent_change_applied") is False, "preview must never persist")
print("live implicit feedback rejection: PASS")


explicit_preview = _post(
    "/decision/feedback-preview",
    {
        "criteria": criteria,
        "explicit": True,
        "criterion_adjustments": {"reliability": 0.10, "cost": -0.10},
        "note": "Reliability matters more.",
    },
)
_assert(explicit_preview.get("applied_in_preview") is True, f"bounded explicit feedback should preview successfully: {explicit_preview}")
_assert(explicit_preview.get("persistent_change_applied") is False, "explicit feedback preview must remain non-persistent")
print("live explicit feedback preview: PASS")


architecture_prompt = (
    "Compare a monolith, modular monolith, and microservices for a small team with "
    "strong consistency and strict auditability requirements. Recommend the best starting architecture."
)
architecture = _post(
    "/chat",
    {
        "message": architecture_prompt,
        "workspace_id": "v021-decision-ws",
        "business_id": "v021-decision-biz",
        "user_id": "v021-decision-user",
    },
)
_assert(architecture.get("status") == "RESPOND", f"architecture chat must respond: {architecture}")
cognitive = architecture.get("cognitive") or {}
decision_meta = cognitive.get("decision") or {}
_assert(decision_meta.get("selected_option") == "modular_monolith", f"chat decision should select modular_monolith: {decision_meta}")
_assert(decision_meta.get("boundary") in {"RECOMMEND", "CONDITIONAL"}, f"chat decision boundary mismatch: {decision_meta}")
_assert(architecture.get("hidden_reasoning_exposed") is False, "chat must preserve hidden reasoning privacy")
print("live /chat decision integration: PASS")


print("SHY v0.21 LEARNING & DECISION CHECKPOINT 2: PASS")
