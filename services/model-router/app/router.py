from dataclasses import dataclass
from typing import Literal

TaskType = Literal[
    "general",
    "reasoning",
    "coding",
    "vision",
    "research",
]

@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    task_type: TaskType
    reason: str

class ModelRouter:
    """
    SHY intelligence router.

    v0.4 intentionally routes every executable request to the verified
    local model. Future providers can be added without changing SHY's identity.
    """

    def __init__(self, local_model: str):
        self.local_model = local_model

    def classify(self, message: str) -> TaskType:
        text = message.lower()

        coding_terms = (
            "code", "python", "javascript", "typescript",
            "react", "debug", "function", "api", "program"
        )

        vision_terms = (
            "image", "photo", "picture", "screenshot", "vision"
        )

        research_terms = (
            "research", "sources", "latest", "search the web",
            "look up", "find online"
        )

        reasoning_terms = (
            "analyze", "reason", "compare", "strategy",
            "plan", "solve", "explain why"
        )

        if any(term in text for term in coding_terms):
            return "coding"

        if any(term in text for term in vision_terms):
            return "vision"

        if any(term in text for term in research_terms):
            return "research"

        if any(term in text for term in reasoning_terms):
            return "reasoning"

        return "general"

    def route(self, message: str) -> ModelRoute:
        task_type = self.classify(message)

        return ModelRoute(
            provider="ollama-local",
            model=self.local_model,
            task_type=task_type,
            reason="Local intelligence is the only enabled provider."
        )
