from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Sequence


class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"


class VoiceIntent(str, Enum):
    CHAT = "CHAT"
    COMPUTER_ACTION = "COMPUTER_ACTION"
    CONFIRM = "CONFIRM"
    CANCEL = "CANCEL"
    UNKNOWN = "UNKNOWN"


class ComputerPermission(str, Enum):
    READ_ONLY = "READ_ONLY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DENIED = "DENIED"


class ComputerActionType(str, Enum):
    READ_SCREEN = "READ_SCREEN"
    OPEN_APPLICATION = "OPEN_APPLICATION"
    NAVIGATE = "NAVIGATE"
    CLICK = "CLICK"
    TYPE_TEXT = "TYPE_TEXT"
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    SEND_MESSAGE = "SEND_MESSAGE"
    PURCHASE = "PURCHASE"
    DELETE = "DELETE"
    SHELL = "SHELL"
    SECURITY_CHANGE = "SECURITY_CHANGE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class VoiceInterpretation:
    normalized_text: str
    intent: VoiceIntent
    next_state: VoiceState
    requires_confirmation: bool
    computer_action: ComputerActionType | None
    permission: ComputerPermission | None


@dataclass(frozen=True)
class ComputerStep:
    index: int
    action: ComputerActionType
    description: str
    permission: ComputerPermission
    requires_confirmation: bool


@dataclass(frozen=True)
class ComputerPlan:
    objective: str
    steps: tuple[ComputerStep, ...]
    permission: ComputerPermission
    requires_confirmation: bool
    denied_reason: str | None
    max_steps_enforced: bool


_CANCEL_PHRASES = (
    "stop",
    "cancel",
    "never mind",
    "nevermind",
    "abort",
)

_CONFIRM_PHRASES = (
    "confirm",
    "yes do it",
    "yes proceed",
    "go ahead",
    "approve",
)

_DENIED_MARKERS = (
    "disable antivirus",
    "disable firewall",
    "turn off security",
    "bypass security",
    "steal password",
    "show password",
    "reveal password",
    "dump credentials",
    "credential theft",
    "keylogger",
    "run arbitrary shell",
    "execute shell command",
    "powershell command",
    "terminal command",
    "delete system32",
)

_READ_ONLY_MARKERS: tuple[tuple[str, ComputerActionType], ...] = (
    ("read the screen", ComputerActionType.READ_SCREEN),
    ("what is on the screen", ComputerActionType.READ_SCREEN),
    ("show me the screen", ComputerActionType.READ_SCREEN),
    ("read file", ComputerActionType.FILE_READ),
    ("open file", ComputerActionType.FILE_READ),
    ("check file", ComputerActionType.FILE_READ),
    ("open app", ComputerActionType.OPEN_APPLICATION),
    ("open application", ComputerActionType.OPEN_APPLICATION),
    ("open browser", ComputerActionType.OPEN_APPLICATION),
    ("go to", ComputerActionType.NAVIGATE),
    ("navigate to", ComputerActionType.NAVIGATE),
)

_STATE_CHANGE_MARKERS: tuple[tuple[str, ComputerActionType], ...] = (
    ("click", ComputerActionType.CLICK),
    ("type ", ComputerActionType.TYPE_TEXT),
    ("write ", ComputerActionType.TYPE_TEXT),
    ("edit file", ComputerActionType.FILE_WRITE),
    ("save file", ComputerActionType.FILE_WRITE),
    ("send message", ComputerActionType.SEND_MESSAGE),
    ("send email", ComputerActionType.SEND_MESSAGE),
    ("purchase", ComputerActionType.PURCHASE),
    ("buy ", ComputerActionType.PURCHASE),
    ("delete", ComputerActionType.DELETE),
)

_SHELL_MARKERS = (
    "shell",
    "terminal",
    "powershell",
    "cmd.exe",
    "command prompt",
    "bash",
)

_COMPUTER_MARKERS = (
    "screen",
    "browser",
    "application",
    "app",
    "file",
    "click",
    "type",
    "write",
    "navigate",
    "open",
    "send",
    "delete",
    "buy",
    "purchase",
    "computer",
    "desktop",
)


def normalize_voice_text(text: str) -> str:
    cleaned = " ".join(str(text or "").strip().split())
    return cleaned


def _lower(text: str) -> str:
    return normalize_voice_text(text).lower()


def _permission_for_action(action: ComputerActionType) -> ComputerPermission:
    if action in {
        ComputerActionType.READ_SCREEN,
        ComputerActionType.OPEN_APPLICATION,
        ComputerActionType.NAVIGATE,
        ComputerActionType.FILE_READ,
    }:
        return ComputerPermission.READ_ONLY
    if action in {
        ComputerActionType.CLICK,
        ComputerActionType.TYPE_TEXT,
        ComputerActionType.FILE_WRITE,
        ComputerActionType.SEND_MESSAGE,
        ComputerActionType.PURCHASE,
        ComputerActionType.DELETE,
    }:
        return ComputerPermission.APPROVAL_REQUIRED
    return ComputerPermission.DENIED


def classify_computer_action(text: str) -> tuple[ComputerActionType, ComputerPermission, str | None]:
    lowered = _lower(text)

    if any(marker in lowered for marker in _DENIED_MARKERS):
        return ComputerActionType.SECURITY_CHANGE, ComputerPermission.DENIED, "security_or_credential_action_denied"

    if any(marker in lowered for marker in _SHELL_MARKERS):
        return ComputerActionType.SHELL, ComputerPermission.DENIED, "arbitrary_shell_execution_denied"

    for marker, action in _STATE_CHANGE_MARKERS:
        if marker in lowered:
            return action, _permission_for_action(action), None

    for marker, action in _READ_ONLY_MARKERS:
        if marker in lowered:
            return action, _permission_for_action(action), None

    if any(marker in lowered for marker in _COMPUTER_MARKERS):
        return ComputerActionType.UNKNOWN, ComputerPermission.APPROVAL_REQUIRED, None

    return ComputerActionType.UNKNOWN, ComputerPermission.DENIED, "computer_action_not_understood"


def interpret_voice_utterance(text: str) -> VoiceInterpretation:
    normalized = normalize_voice_text(text)
    lowered = normalized.lower()

    if not normalized:
        return VoiceInterpretation(
            normalized_text="",
            intent=VoiceIntent.UNKNOWN,
            next_state=VoiceState.LISTENING,
            requires_confirmation=False,
            computer_action=None,
            permission=None,
        )

    if any(lowered == phrase or lowered.startswith(phrase + " ") for phrase in _CANCEL_PHRASES):
        return VoiceInterpretation(
            normalized_text=normalized,
            intent=VoiceIntent.CANCEL,
            next_state=VoiceState.INTERRUPTED,
            requires_confirmation=False,
            computer_action=None,
            permission=None,
        )

    if any(lowered == phrase or lowered.startswith(phrase + " ") for phrase in _CONFIRM_PHRASES):
        return VoiceInterpretation(
            normalized_text=normalized,
            intent=VoiceIntent.CONFIRM,
            next_state=VoiceState.PROCESSING,
            requires_confirmation=False,
            computer_action=None,
            permission=None,
        )

    if any(marker in lowered for marker in _COMPUTER_MARKERS):
        action, permission, _ = classify_computer_action(normalized)
        requires_confirmation = permission == ComputerPermission.APPROVAL_REQUIRED
        return VoiceInterpretation(
            normalized_text=normalized,
            intent=VoiceIntent.COMPUTER_ACTION,
            next_state=VoiceState.AWAITING_CONFIRMATION if requires_confirmation else VoiceState.PROCESSING,
            requires_confirmation=requires_confirmation,
            computer_action=action,
            permission=permission,
        )

    return VoiceInterpretation(
        normalized_text=normalized,
        intent=VoiceIntent.CHAT,
        next_state=VoiceState.PROCESSING,
        requires_confirmation=False,
        computer_action=None,
        permission=None,
    )


def build_computer_plan(
    objective: str,
    *,
    max_steps: int = 8,
) -> ComputerPlan:
    normalized = normalize_voice_text(objective)
    action, permission, denied_reason = classify_computer_action(normalized)

    bounded_max_steps = max(1, min(int(max_steps), 12))
    if permission == ComputerPermission.DENIED:
        return ComputerPlan(
            objective=normalized,
            steps=(),
            permission=permission,
            requires_confirmation=False,
            denied_reason=denied_reason,
            max_steps_enforced=True,
        )

    descriptions: list[tuple[ComputerActionType, str]] = []
    lowered = normalized.lower()

    if action == ComputerActionType.OPEN_APPLICATION:
        descriptions.append((action, "Open the requested application without changing user data."))
    elif action == ComputerActionType.NAVIGATE:
        descriptions.append((action, "Navigate to the requested destination without submitting forms."))
    elif action == ComputerActionType.READ_SCREEN:
        descriptions.append((action, "Inspect visible screen content without making changes."))
    elif action == ComputerActionType.FILE_READ:
        descriptions.append((action, "Open and read the requested file without modifying it."))
    elif action == ComputerActionType.CLICK:
        descriptions.append((ComputerActionType.READ_SCREEN, "Inspect the current screen state before acting."))
        descriptions.append((action, "Click the requested control after approval."))
    elif action == ComputerActionType.TYPE_TEXT:
        descriptions.append((ComputerActionType.READ_SCREEN, "Inspect the target field before typing."))
        descriptions.append((action, "Type the requested text after approval."))
    elif action == ComputerActionType.FILE_WRITE:
        descriptions.append((ComputerActionType.FILE_READ, "Read the current file state before modification."))
        descriptions.append((action, "Apply the requested file change after approval."))
    elif action == ComputerActionType.SEND_MESSAGE:
        descriptions.append((ComputerActionType.READ_SCREEN, "Review the recipient and composed message."))
        descriptions.append((action, "Send the message only after approval."))
    elif action == ComputerActionType.PURCHASE:
        descriptions.append((ComputerActionType.READ_SCREEN, "Review item, price, merchant, and destination."))
        descriptions.append((action, "Submit the purchase only after explicit approval."))
    elif action == ComputerActionType.DELETE:
        descriptions.append((ComputerActionType.READ_SCREEN, "Verify the exact target and consequences."))
        descriptions.append((action, "Delete only after explicit approval."))
    else:
        descriptions.append((action, "Prepare the requested computer action for approval."))

    steps: list[ComputerStep] = []
    for index, (step_action, description) in enumerate(descriptions[:bounded_max_steps], start=1):
        step_permission = _permission_for_action(step_action)
        steps.append(
            ComputerStep(
                index=index,
                action=step_action,
                description=description,
                permission=step_permission,
                requires_confirmation=step_permission == ComputerPermission.APPROVAL_REQUIRED,
            )
        )

    overall_permission = (
        ComputerPermission.APPROVAL_REQUIRED
        if any(step.permission == ComputerPermission.APPROVAL_REQUIRED for step in steps)
        else ComputerPermission.READ_ONLY
    )
    return ComputerPlan(
        objective=normalized,
        steps=tuple(steps),
        permission=overall_permission,
        requires_confirmation=overall_permission == ComputerPermission.APPROVAL_REQUIRED,
        denied_reason=None,
        max_steps_enforced=len(descriptions) <= bounded_max_steps,
    )


def public_voice_metadata(result: VoiceInterpretation) -> dict[str, object]:
    return {
        "intent": result.intent.value,
        "next_state": result.next_state.value,
        "requires_confirmation": result.requires_confirmation,
        "computer_action": result.computer_action.value if result.computer_action else None,
        "permission": result.permission.value if result.permission else None,
    }


def public_computer_plan(plan: ComputerPlan) -> dict[str, object]:
    return {
        "objective": plan.objective,
        "permission": plan.permission.value,
        "requires_confirmation": plan.requires_confirmation,
        "denied_reason": plan.denied_reason,
        "max_steps_enforced": plan.max_steps_enforced,
        "steps": [
            {
                "index": step.index,
                "action": step.action.value,
                "description": step.description,
                "permission": step.permission.value,
                "requires_confirmation": step.requires_confirmation,
            }
            for step in plan.steps
        ],
    }
