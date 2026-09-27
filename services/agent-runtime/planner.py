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

        research_prefixes = (
            "research ",
            "search the web ",
            "search online ",
            "look up ",
            "find online ",
        )

        for prefix in research_prefixes:
            if text.startswith(prefix):
                query = message.strip()[len(prefix):].strip()

                if query:
                    return AgentStep(
                        step_type=StepType.TOOL,
                        reason="The request requires current public web research.",
                        tool_name="web.search",
                        arguments={
                            "query": query,
                            "max_results": 5,
                        },
                    )

        return AgentStep(
            step_type=StepType.RESPOND,
            reason="No tool is required for this request.",
        )
