"""Hard character and message budgets for model history, including fallback paths."""
from __future__ import annotations

from dataclasses import dataclass

TRUNCATION_MARKER = "[Context excerpt truncated]\n"


@dataclass(frozen=True)
class BoundedContext:
    messages: tuple[dict[str, str], ...]
    context_chars: int
    omitted_messages: int
    clipped_messages: int


def bound_context(messages: list[dict], max_chars: int, max_messages: int) -> BoundedContext:
    if not isinstance(max_chars, int) or not isinstance(max_messages, int) or max_chars < 0 or max_messages < 0:
        raise ValueError("nonnegative_integer_context_limits_required")
    valid = [item for item in messages if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
             and isinstance(item.get("content"), str) and item["content"].strip()]
    selected = []
    used = clipped = 0
    # Retain recent history first, then restore chronological order. One boundary
    # excerpt may be clipped, with an explicit marker inside the same budget.
    for item in reversed(valid[-max_messages:] if max_messages else []):
        remaining = max_chars - used
        if remaining <= 0:
            break
        text = item["content"]
        if len(text) > remaining:
            if remaining <= len(TRUNCATION_MARKER):
                break
            text = TRUNCATION_MARKER + text[:remaining - len(TRUNCATION_MARKER)]
            clipped += 1
        selected.append({"role": item["role"], "content": text})
        used += len(text)
    return BoundedContext(tuple(reversed(selected)), used, len(valid) - len(selected), clipped)
