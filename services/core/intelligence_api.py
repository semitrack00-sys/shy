"""Stateless API: the scope field filters supplied data and does not authenticate a user."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from agent_runtime.intelligence.common import MAX_BYTES
from agent_runtime.intelligence.registry import catalog, evaluate

router = APIRouter(prefix="/intelligence", tags=["Bounded intelligence"])


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    capability: str = Field(min_length=1, max_length=100)
    payload: dict


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    requests: list[EvaluationRequest] = Field(min_length=1, max_length=10)


@router.get("/capabilities")
def capabilities():
    return {"capabilities": catalog(), "capability_count": 50, "mode": "stateless_supplied_data", "scope_authenticated": False, "external_execution": False}


@router.post("/evaluate")
def evaluate_request(request: EvaluationRequest):
    result = evaluate(request.capability, request.payload)
    if result["boundary"] == "UNAVAILABLE":
        raise HTTPException(status_code=404, detail=result)
    if result["boundary"] == "INPUT_REQUIRED":
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/batch")
def evaluate_batch(request: BatchRequest):
    # Every result is independent and preserves its own failure boundary.
    results = [evaluate(item.capability, item.payload) for item in request.requests]
    return {"results": results, "all_evaluated": all(x["boundary"] == "EVALUATED" for x in results), "side_effect_performed": False}


class IntelligenceBodyLimit:
    """Bound streamed bodies before FastAPI parses JSON, including absent Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path", "").rstrip("/") not in {"/intelligence/evaluate", "/intelligence/batch"}:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BYTES:
                response = json.dumps({"detail": "intelligence_request_byte_limit_exceeded"}).encode()
                await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(response)).encode())]})
                await send({"type": "http.response.body", "body": response})
                return
            if not message.get("more_body", False):
                break
        # Reject deeply nested or nonstandard JSON before the framework decoder can recurse.
        try:
            depth = 0
            quoted = False
            escaped = False
            for char in body.decode("utf-8"):
                if quoted:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        quoted = False
                elif char == '"':
                    quoted = True
                elif char in "[{":
                    depth += 1
                    if depth > 16:
                        raise ValueError("intelligence_json_depth_exceeded")
                elif char in "]}":
                    depth -= 1
            json.loads(body, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite_json_number")))
        except (ValueError, UnicodeError, RecursionError):
            response = b'{"detail":"invalid_or_excessively_nested_intelligence_json"}'
            await send({"type": "http.response.start", "status": 422, "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": response})
            return
        consumed = False
        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)
