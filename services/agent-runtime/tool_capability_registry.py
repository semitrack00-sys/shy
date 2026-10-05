from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class ToolPermission(str, Enum):
    READ_ONLY = "READ_ONLY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DENIED = "DENIED"


class ToolRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class ToolCapability:
    tool_id: str
    capabilities: tuple[str, ...]
    permission: ToolPermission
    risk: ToolRisk
    scopes: tuple[str, ...]
    side_effects: bool = False
    available: bool = True


@dataclass(frozen=True)
class ToolRegistryResult:
    accepted: bool
    tools: tuple[ToolCapability, ...]
    reason: str | None


@dataclass(frozen=True)
class ToolSelection:
    selected_tool_id: str | None
    candidates: tuple[str, ...]
    permission: ToolPermission | None
    approval_required: bool
    reason: str


_DENIED_CAPABILITY_MARKERS = (
    "arbitrary_shell",
    "credential_dump",
    "disable_security",
    "bypass_approval",
)


def _clean(value: str, limit: int = 200) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def validate_registry(tools: Sequence[ToolCapability], *, max_tools: int = 128) -> ToolRegistryResult:
    bound = max(1, min(int(max_tools), 512))
    selected = tuple(tools[:bound])
    seen: set[str] = set()
    clean: list[ToolCapability] = []

    for tool in selected:
        tool_id = _clean(tool.tool_id)
        if not tool_id:
            return ToolRegistryResult(False, (), "tool_id_required")
        if tool_id in seen:
            return ToolRegistryResult(False, (), "duplicate_tool_id")
        seen.add(tool_id)

        capabilities = tuple(sorted({_clean(item) for item in tool.capabilities if _clean(item)}))
        scopes = tuple(sorted({_clean(item) for item in tool.scopes if _clean(item)}))
        if not capabilities:
            return ToolRegistryResult(False, (), "tool_capability_required")
        if not scopes:
            return ToolRegistryResult(False, (), "tool_scope_required")
        if any(marker in cap.lower().replace(" ", "_") for cap in capabilities for marker in _DENIED_CAPABILITY_MARKERS):
            return ToolRegistryResult(False, (), "denied_tool_capability")
        if tool.side_effects and tool.permission != ToolPermission.APPROVAL_REQUIRED:
            return ToolRegistryResult(False, (), "side_effect_tool_requires_approval")
        if tool.risk == ToolRisk.HIGH and tool.permission == ToolPermission.READ_ONLY and tool.side_effects:
            return ToolRegistryResult(False, (), "high_risk_side_effect_requires_approval")

        clean.append(
            ToolCapability(
                tool_id=tool_id,
                capabilities=capabilities,
                permission=tool.permission,
                risk=tool.risk,
                scopes=scopes,
                side_effects=bool(tool.side_effects),
                available=bool(tool.available),
            )
        )

    return ToolRegistryResult(True, tuple(clean), None)


def select_tool(
    registry: ToolRegistryResult,
    *,
    capability: str,
    scope: str,
    max_candidates: int = 8,
) -> ToolSelection:
    if not registry.accepted:
        return ToolSelection(None, (), None, False, "registry_invalid")

    need = _clean(capability).lower()
    scope_key = _clean(scope).lower()
    if not need or not scope_key:
        return ToolSelection(None, (), None, False, "capability_and_scope_required")

    candidates = [
        tool
        for tool in registry.tools
        if tool.available
        and any(cap.lower() == need for cap in tool.capabilities)
        and any(item.lower() == scope_key for item in tool.scopes)
        and tool.permission != ToolPermission.DENIED
    ]
    rank = {ToolRisk.LOW: 0, ToolRisk.MEDIUM: 1, ToolRisk.HIGH: 2}
    candidates.sort(key=lambda item: (rank[item.risk], item.side_effects, item.tool_id))
    candidates = candidates[: max(1, min(int(max_candidates), 32))]

    if not candidates:
        return ToolSelection(None, (), None, False, "no_eligible_tool")

    selected = candidates[0]
    return ToolSelection(
        selected_tool_id=selected.tool_id,
        candidates=tuple(item.tool_id for item in candidates),
        permission=selected.permission,
        approval_required=selected.permission == ToolPermission.APPROVAL_REQUIRED,
        reason="selected_by_capability_scope_and_risk",
    )


def public_tool_registry(registry: ToolRegistryResult) -> dict[str, object]:
    return {
        "accepted": registry.accepted,
        "reason": registry.reason,
        "tool_count": len(registry.tools),
        "tools": [
            {
                "tool_id": tool.tool_id,
                "capabilities": list(tool.capabilities),
                "permission": tool.permission.value,
                "risk": tool.risk.value,
                "scopes": list(tool.scopes),
                "side_effects": tool.side_effects,
                "available": tool.available,
            }
            for tool in registry.tools
        ],
    }


def public_tool_selection(selection: ToolSelection) -> dict[str, object]:
    return {
        "selected_tool_id": selection.selected_tool_id,
        "candidates": list(selection.candidates),
        "permission": selection.permission.value if selection.permission else None,
        "approval_required": selection.approval_required,
        "reason": selection.reason,
        "execution_performed": False,
    }
