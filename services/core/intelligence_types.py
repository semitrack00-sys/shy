from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    CHAT = "CHAT"
    REASONING = "REASONING"
    RESEARCH = "RESEARCH"
    CODING = "CODING"
    MEMORY = "MEMORY"
    TOOL = "TOOL"
    MULTI_STEP = "MULTI_STEP"


class Complexity(str, Enum):
    SIMPLE = "SIMPLE"
    MODERATE = "MODERATE"
    COMPLEX = "COMPLEX"


class ReasonCode(str, Enum):
    SIMPLE_CONVERSATION = "SIMPLE_CONVERSATION"
    CURRENT_INFORMATION_REQUIRED = "CURRENT_INFORMATION_REQUIRED"
    EXPLICIT_RESEARCH_REQUEST = "EXPLICIT_RESEARCH_REQUEST"
    MULTI_CONSTRAINT_TASK = "MULTI_CONSTRAINT_TASK"
    TOOL_REQUIRED = "TOOL_REQUIRED"
    MEMORY_CONTEXT_REQUIRED = "MEMORY_CONTEXT_REQUIRED"


@dataclass(frozen=True)
class IntelligenceDecision:
    primary_capability: Capability
    secondary_capabilities: tuple[Capability, ...] = ()
    complexity: Complexity = Complexity.SIMPLE
    requires_external_evidence: bool = False
    requires_tool: bool = False
    requires_memory: bool = False
    verification_required: bool = False
    confidence: float = 0.5
    reason_code: ReasonCode = ReasonCode.SIMPLE_CONVERSATION

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
