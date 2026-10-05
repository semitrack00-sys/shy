from __future__ import annotations

from . import data, operations, retrieval, security, workflows
from .common import digest, validate_payload

CAPABILITIES = tuple(item for module in (retrieval, workflows, data, security, operations) for item in module.CAPABILITIES)
HANDLERS = {name: (version, handler) for version, name, handler in CAPABILITIES}

if len(HANDLERS) != 50 or tuple(x[0] for x in CAPABILITIES) != tuple(range(51, 101)):
    raise RuntimeError("intelligence_milestone_registry_incomplete")


def catalog() -> list[dict]:
    return [{"capability_id": name, "introduced_version": f"0.{version}.0", "state": "BOUNDED", "input": "supplied_json_only", "persistent_change_applied": False, "external_execution": False} for version, name, _ in CAPABILITIES]


def evaluate(capability: str, payload: dict) -> dict:
    if not isinstance(capability, str) or capability not in HANDLERS:
        return {"capability": capability if isinstance(capability, str) else None, "boundary": "UNAVAILABLE", "reason": "unknown_capability", "payload": {}, "side_effect_performed": False}
    version, handler = HANDLERS[capability]
    try:
        if not isinstance(payload, dict):
            raise ValueError("payload_object_required")
        validate_payload(payload)
        result = handler(payload)
        # Enforce output bounds and finite JSON too; arithmetic must not emit infinity.
        validate_payload(result)
    except ValueError as exc:
        return {"capability": capability, "introduced_version": f"0.{version}.0", "boundary": "INPUT_REQUIRED", "reason": str(exc), "payload": {}, "side_effect_performed": False}
    except ArithmeticError:
        return {"capability": capability, "introduced_version": f"0.{version}.0", "boundary": "INPUT_REQUIRED", "reason": "numerical_range_exceeded", "payload": {}, "side_effect_performed": False}
    return {"capability": capability, "introduced_version": f"0.{version}.0", "boundary": "EVALUATED", "payload": result, "input_sha256": digest(payload), "side_effect_performed": False, "result_is_authorization": False, "hidden_reasoning_exposed": False}
