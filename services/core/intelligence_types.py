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
    CODING_TASK_CLASSIFIED = "CODING_TASK_CLASSIFIED"
    CODING_FALSE_POSITIVE_PROTECTED = "CODING_FALSE_POSITIVE_PROTECTED"


class CodingTaskType(str, Enum):
    UNKNOWN = "UNKNOWN"
    DEBUG_EXCEPTION = "DEBUG_EXCEPTION"
    STACK_TRACE_ANALYSIS = "STACK_TRACE_ANALYSIS"
    REACT_BUILD_FAILURE = "REACT_BUILD_FAILURE"
    GRADLE_BUILD_FAILURE = "GRADLE_BUILD_FAILURE"
    API_IMPLEMENTATION = "API_IMPLEMENTATION"
    UNIT_TEST_GENERATION = "UNIT_TEST_GENERATION"
    REFACTORING = "REFACTORING"
    GIT_DIFF_REVIEW = "GIT_DIFF_REVIEW"
    REPOSITORY_ANALYSIS = "REPOSITORY_ANALYSIS"


@dataclass(frozen=True)
class CodingTaskProfile:
    task_type: CodingTaskType = CodingTaskType.UNKNOWN
    languages: tuple[str, ...] = ()
    frameworks: tuple[str, ...] = ()
    repository_context_required: bool = False
    execution_required: bool = False
    verification_required: bool = False
    complexity: Complexity = Complexity.MODERATE
    reason_code: ReasonCode = ReasonCode.CODING_TASK_CLASSIFIED


@dataclass(frozen=True)
class RepositoryContextInput:
    repository_identifier: str = ""
    branch: str = ""
    commit: str = ""
    relevant_files: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    test_results: tuple[str, ...] = ()
    diff_summary: str = ""


@dataclass(frozen=True)
class IntelligenceDecision:
    primary_capability: Capability
    secondary_capabilities: tuple[Capability, ...] = ()
    complexity: Complexity = Complexity.SIMPLE
    requires_external_evidence: bool = False
    requires_tool: bool = False
    requires_memory: bool = False
    verification_required: bool = False
    repository_context_required: bool = False
    execution_required: bool = False
    coding_profile: CodingTaskProfile | None = None
    confidence: float = 0.5
    reason_code: ReasonCode = ReasonCode.SIMPLE_CONVERSATION

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
