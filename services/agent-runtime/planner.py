from dataclasses import dataclass
from enum import Enum
from typing import Any


class StepType(str, Enum):
    RESPOND = "RESPOND"
    TOOL = "TOOL"


@dataclass(frozen=True)
class AgentStep:
    step_type: StepType
    reason: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None


class AgentPlanner:
    """
    SHY Agent Planner v0.7.

    The planner may propose an action.
    It cannot execute tools and cannot grant approval.
    """

    def plan(self, message: str) -> AgentStep:
        text = message.lower().strip()

        health_phrases = (
            "system health",
            "shy health",
            "health status",
            "are you healthy",
            "check your health",
        )

        if any(phrase in text for phrase in health_phrases):
            return AgentStep(
                step_type=StepType.TOOL,
                reason="The request requires SHY system health information.",
                tool_name="system.health",
                arguments={},
            )

        return AgentStep(
            step_type=StepType.RESPOND,
            reason="No tool is required for this request.",
        )
