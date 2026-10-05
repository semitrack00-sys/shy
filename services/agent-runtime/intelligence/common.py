from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any

MAX_BYTES = 262144
MAX_ITEMS = 500


def validate_payload(value: Any, depth: int = 0) -> None:
    if depth > 12:
        raise ValueError("payload_depth_exceeded")
    if isinstance(value, dict):
        if len(value) > MAX_ITEMS or any(not isinstance(k, str) or len(k) > 200 for k in value):
            raise ValueError("invalid_object_size_or_key")
        for item in value.values():
            validate_payload(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_ITEMS:
            raise ValueError("item_limit_exceeded")
        for item in value:
            validate_payload(item, depth + 1)
    elif isinstance(value, str):
        if len(value) > 16000:
            raise ValueError("text_limit_exceeded")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite_number")
    elif value is not None and not isinstance(value, (int, bool)):
        raise ValueError("json_value_required")
    elif isinstance(value, int) and not isinstance(value, bool) and abs(value) > 10**15:
        raise ValueError("integer_limit_exceeded")
    if depth == 0 and len(canonical(value).encode()) > MAX_BYTES:
        raise ValueError("payload_byte_limit_exceeded")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value: Any, name: str = "text") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}_required")
    return value


def number(value: Any, name: str = "number", minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}_must_be_finite_number")
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{name}_below_minimum")
    return result


def integer(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name}_must_be_integer_{low}_to_{high}")
    return value


def rows(payload: dict, name: str, *, allow_empty: bool = False) -> list[dict]:
    result = payload.get(name)
    if not isinstance(result, list) or (not result and not allow_empty) or any(not isinstance(x, dict) for x in result):
        raise ValueError(f"{name}_must_be_object_list")
    return result


def unique_ids(items: list[dict], key: str = "id") -> None:
    ids = [text(item.get(key), key) for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate_{key}")


def tokens(value: str) -> list[str]:
    return re.findall(r"[^\W_]+", value.casefold(), re.UNICODE)


def timestamp(value: Any, name: str = "timestamp") -> datetime:
    try:
        parsed = datetime.fromisoformat(text(value, name).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name}_must_be_iso8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name}_timezone_required")
    return parsed.astimezone(timezone.utc)


def numeric_values(payload: dict, key: str = "values", *, nonnegative: bool = False) -> list[float]:
    values = payload.get(key)
    if not isinstance(values, list) or not values:
        raise ValueError(f"{key}_required")
    return [number(x, key, 0 if nonnegative else None) for x in values]


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lower = math.floor(pos)
    return ordered[lower] + (ordered[math.ceil(pos)] - ordered[lower]) * (pos - lower)
