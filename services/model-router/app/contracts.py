from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelCapability(str, Enum):
    CHAT = "CHAT"
    REASONING = "REASONING"
    DEEP_REASONING = "DEEP_REASONING"
    CODING = "CODING"
    RESEARCH_SYNTHESIS = "RESEARCH_SYNTHESIS"
    VISION = "VISION"
    AUDIO = "AUDIO"
    TOOL_USE = "TOOL_USE"
    STRUCTURED_OUTPUT = "STRUCTURED_OUTPUT"
    LONG_CONTEXT = "LONG_CONTEXT"


class PrivacyClass(str, Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    PRIVATE_REMOTE_ALLOWED = "PRIVATE_REMOTE_ALLOWED"
    REMOTE_ALLOWED = "REMOTE_ALLOWED"


class CostClass(str, Enum):
    LOCAL = "LOCAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LatencyClass(str, Enum):
    FAST = "FAST"
    NORMAL = "NORMAL"
    SLOW = "SLOW"


class QualityClass(str, Enum):
    STANDARD = "STANDARD"
    HIGH = "HIGH"
    FRONTIER = "FRONTIER"


class ProviderHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class SelectionReasonCode(str, Enum):
    LOCAL_SUFFICIENT = "LOCAL_SUFFICIENT"
    FRONTIER_REQUIRED = "FRONTIER_REQUIRED"
    DEEP_REASONING_REQUIRED = "DEEP_REASONING_REQUIRED"
    CODING_SPECIALIST_REQUIRED = "CODING_SPECIALIST_REQUIRED"
    PRIVACY_LOCAL_REQUIRED = "PRIVACY_LOCAL_REQUIRED"
    PRIMARY_UNAVAILABLE_FALLBACK = "PRIMARY_UNAVAILABLE_FALLBACK"
    VERIFICATION_ESCALATION = "VERIFICATION_ESCALATION"
    CAPABILITY_MATCH = "CAPABILITY_MATCH"
    ATTEMPT_LIMIT_REACHED = "ATTEMPT_LIMIT_REACHED"
    NO_CAPABLE_MODEL = "NO_CAPABLE_MODEL"
    PRIVACY_POLICY_BLOCKED = "PRIVACY_POLICY_BLOCKED"


class ModelFailureCategory(str, Enum):
    NO_CAPABLE_MODEL = "NO_CAPABLE_MODEL"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    MODEL_ERROR = "MODEL_ERROR"
    TIMEOUT = "TIMEOUT"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    ATTEMPT_LIMIT_REACHED = "ATTEMPT_LIMIT_REACHED"
    ESCALATION_LIMIT_REACHED = "ESCALATION_LIMIT_REACHED"
    PRIVACY_POLICY_BLOCKED = "PRIVACY_POLICY_BLOCKED"


class VerificationEscalationAction(str, Enum):
    RETRY_SAME_MODEL = "RETRY_SAME_MODEL"
    TRY_FALLBACK = "TRY_FALLBACK"
    ESCALATE_MODEL = "ESCALATE_MODEL"
    STOP = "STOP"


@dataclass(frozen=True)
class ProviderHealth:
    provider_id: str
    status: ProviderHealthStatus
    detail: str = ""


@dataclass(frozen=True)
class ModelProfile:
    model_id: str
    provider_id: str
    display_name: str
    capabilities: tuple[ModelCapability, ...]
    context_window: int
    supports_tools: bool
    supports_vision: bool
    supports_structured_output: bool
    local: bool
    privacy_class: PrivacyClass
    cost_class: CostClass
    latency_class: LatencyClass
    quality_class: QualityClass
    enabled: bool = True

    def __post_init__(self):
        if not self.model_id.strip():
            raise ValueError("model_id is required")
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if not self.display_name.strip():
            raise ValueError("display_name is required")
        if self.context_window <= 0:
            raise ValueError("context_window must be > 0")
        if not self.capabilities:
            raise ValueError("capabilities cannot be empty")


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ModelRequest:
    messages: tuple[ModelMessage, ...]
    capability: ModelCapability
    system_instruction: str = ""
    temperature: float | None = None
    max_output_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class ModelResponse:
    provider_id: str
    model_id: str
    status: str
    content: str
    finish_reason: str | None = None
    usage: ModelUsage | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelSelectionDecision:
    selected_provider_id: str
    selected_model_id: str
    required_capability: ModelCapability
    selection_reason_code: SelectionReasonCode
    fallback_candidates: tuple[str, ...]
    escalation_allowed: bool
    confidence: float


@dataclass(frozen=True)
class OrchestrationFailure:
    category: ModelFailureCategory
    reason_code: str
    safe_message: str


@dataclass(frozen=True)
class OrchestrationResult:
    decision: ModelSelectionDecision | None
    response: ModelResponse | None
    attempts_used: int
    escalations_used: int
    failure: OrchestrationFailure | None
