import importlib.util
from pathlib import Path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


services_path = Path(__file__).resolve().parents[1]

types_module = load_module(
    "shy_intelligence_types",
    services_path / "core" / "intelligence_types.py",
)

Capability = types_module.Capability
Complexity = types_module.Complexity
IntelligenceDecision = types_module.IntelligenceDecision
ReasonCode = types_module.ReasonCode


class IntelligenceRouter:
    """
    Phase 1 capability router.

    This router performs deterministic capability classification.
    It does not execute tools and does not call an LLM.
    """

    def analyze(self, message: str) -> IntelligenceDecision:
        text = " ".join(message.lower().split())

        if not text:
            return IntelligenceDecision(
                primary_capability=Capability.CHAT,
                complexity=Complexity.SIMPLE,
                confidence=0.5,
                reason_code=ReasonCode.SIMPLE_CONVERSATION,
            )

        if self._is_explicit_tool_request(text):
            return IntelligenceDecision(
                primary_capability=Capability.TOOL,
                complexity=Complexity.MODERATE,
                requires_tool=True,
                confidence=0.93,
                reason_code=ReasonCode.TOOL_REQUIRED,
            )

        if self._is_research_request(text):
            reason_code = ReasonCode.EXPLICIT_RESEARCH_REQUEST

            if self._needs_current_information(text):
                reason_code = ReasonCode.CURRENT_INFORMATION_REQUIRED

            return IntelligenceDecision(
                primary_capability=Capability.RESEARCH,
                secondary_capabilities=(Capability.REASONING,),
                complexity=Complexity.MODERATE,
                requires_external_evidence=True,
                requires_tool=True,
                verification_required=True,
                confidence=0.92,
                reason_code=reason_code,
            )

        if self._is_memory_request(text):
            return IntelligenceDecision(
                primary_capability=Capability.MEMORY,
                secondary_capabilities=(Capability.CHAT,),
                complexity=Complexity.MODERATE,
                requires_memory=True,
                confidence=0.84,
                reason_code=ReasonCode.MEMORY_CONTEXT_REQUIRED,
            )

        if self._is_coding_request(text):
            return IntelligenceDecision(
                primary_capability=Capability.CODING,
                secondary_capabilities=(Capability.REASONING,),
                complexity=Complexity.MODERATE,
                verification_required=True,
                confidence=0.88,
                reason_code=ReasonCode.MULTI_CONSTRAINT_TASK,
            )

        if self._is_multi_step_request(text):
            return IntelligenceDecision(
                primary_capability=Capability.MULTI_STEP,
                secondary_capabilities=(Capability.REASONING,),
                complexity=Complexity.COMPLEX,
                verification_required=True,
                confidence=0.9,
                reason_code=ReasonCode.MULTI_CONSTRAINT_TASK,
            )

        if self._is_reasoning_request(text):
            return IntelligenceDecision(
                primary_capability=Capability.REASONING,
                complexity=Complexity.MODERATE,
                verification_required=True,
                confidence=0.78,
                reason_code=ReasonCode.MULTI_CONSTRAINT_TASK,
            )

        return IntelligenceDecision(
            primary_capability=Capability.CHAT,
            complexity=Complexity.SIMPLE,
            confidence=0.72,
            reason_code=ReasonCode.SIMPLE_CONVERSATION,
        )

    @staticmethod
    def _is_explicit_tool_request(text: str) -> bool:
        tool_terms = (
            "use system health",
            "system health",
            "check your health",
            "run tool",
        )
        return any(term in text for term in tool_terms)

    @staticmethod
    def _is_research_request(text: str) -> bool:
        research_terms = (
            "research ",
            "search the web",
            "search online",
            "look up ",
            "find online",
            "latest developments",
        )
        return any(term in text for term in research_terms)

    @staticmethod
    def _needs_current_information(text: str) -> bool:
        freshness_terms = (
            "latest",
            "current",
            "today",
            "recent",
            "developments",
        )
        return any(term in text for term in freshness_terms)

    @staticmethod
    def _is_memory_request(text: str) -> bool:
        memory_terms = (
            "as we discussed",
            "earlier in this conversation",
            "remember that",
            "from previous messages",
            "conversation context",
        )
        return any(term in text for term in memory_terms)

    @staticmethod
    def _is_coding_request(text: str) -> bool:
        coding_terms = (
            "fix this python",
            "fix this function",
            "debug",
            "refactor",
            "write code",
            "typescript",
            "javascript",
            "api endpoint",
            "unit test",
        )
        return any(term in text for term in coding_terms)

    @staticmethod
    def _is_multi_step_request(text: str) -> bool:
        multi_step_terms = (
            "multi-stage",
            "multi step",
            "five constraints",
            "develop a plan",
            "implementation plan",
            "roadmap",
        )
        return any(term in text for term in multi_step_terms)

    @staticmethod
    def _is_reasoning_request(text: str) -> bool:
        reasoning_terms = (
            "compare",
            "tradeoff",
            "analyze",
            "strategy",
            "explain",
            "why",
        )
        return any(term in text for term in reasoning_terms)
