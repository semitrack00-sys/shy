from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class CapabilityState(str, Enum):
    ACTIVE = "ACTIVE"
    BOUNDED = "BOUNDED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class PlatformCapability:
    capability_id: str
    introduced_version: str
    state: CapabilityState
    safety_boundary: str


@dataclass(frozen=True)
class PlatformManifest:
    version: str
    capabilities: tuple[PlatformCapability, ...]
    sequence_complete: bool
    required_disabled_invariants_hold: bool


_REQUIRED_SEQUENCE = (
    "0.20.0",
    "0.21.0",
    "0.22.0",
    "0.23.0",
    "0.24.0",
    "0.25.0",
    "0.26.0",
    "0.27.0",
    "0.28.0",
    "0.29.0",
    "0.30.0",
    "0.31.0",
    "0.32.0",
    "0.33.0",
    "0.34.0",
    "0.35.0",
    "0.36.0",
    "0.37.0",
    "0.38.0",
    "0.39.0",
    "0.40.0",
    "0.41.0",
    "0.42.0",
    "0.43.0",
    "0.44.0",
    "0.45.0",
)


_DEFAULT_CAPABILITIES = (
    PlatformCapability("expert_intelligence", "0.20.0", CapabilityState.ACTIVE, "evidence_and_risk_bounded"),
    PlatformCapability("learning_decision", "0.21.0", CapabilityState.BOUNDED, "verified_outcomes_only"),
    PlatformCapability("voice_interpretation", "0.22.0", CapabilityState.BOUNDED, "transcript_only_no_audio_provider"),
    PlatformCapability("computer_planning", "0.22.0", CapabilityState.BOUNDED, "no_unrestricted_execution"),
    PlatformCapability("vision_reasoning", "0.23.0", CapabilityState.BOUNDED, "provider_and_provenance_required"),
    PlatformCapability("multimodal_fusion", "0.24.0", CapabilityState.ACTIVE, "conflict_detection_and_source_bounds"),
    PlatformCapability("goal_orchestration", "0.25.0", CapabilityState.BOUNDED, "approval_pauses_and_step_limits"),
    PlatformCapability("preference_context", "0.26.0", CapabilityState.BOUNDED, "explicit_or_verified_non_sensitive_only"),
    PlatformCapability("knowledge_graph", "0.27.0", CapabilityState.BOUNDED, "scope_and_provenance_required"),
    PlatformCapability("reliability_self_evaluation", "0.28.0", CapabilityState.BOUNDED, "no_self_certification_or_self_modification"),
    PlatformCapability("tool_capability_registry", "0.29.0", CapabilityState.BOUNDED, "selection_only_no_execution"),
    PlatformCapability("raw_audio_capture", "0.30.0", CapabilityState.DISABLED, "provider_not_connected"),
    PlatformCapability("raw_image_inference", "0.30.0", CapabilityState.DISABLED, "provider_not_connected"),
    PlatformCapability("unrestricted_computer_execution", "0.30.0", CapabilityState.DISABLED, "approval_and_tool_gateway_required"),
    PlatformCapability("arbitrary_shell_execution", "0.30.0", CapabilityState.DISABLED, "explicitly_denied"),
    PlatformCapability("real_person_identity_recognition", "0.30.0", CapabilityState.DISABLED, "not_supported"),
    PlatformCapability("autonomous_security_policy_rewrite", "0.30.0", CapabilityState.DISABLED, "protected_policy"),
    PlatformCapability("temporal_intelligence", "0.31.0", CapabilityState.BOUNDED, "planning_only_no_external_schedule_creation"),
    PlatformCapability("condition_intelligence", "0.32.0", CapabilityState.BOUNDED, "evaluation_only_no_monitoring_or_notifications"),
    PlatformCapability("collaboration_delegation", "0.33.0", CapabilityState.BOUNDED, "planning_only_no_dispatch_or_permission_expansion"),
    PlatformCapability("recovery_rollback", "0.34.0", CapabilityState.BOUNDED, "verified_checkpoint_planning_only_no_rollback_execution"),
    PlatformCapability("document_intelligence", "0.35.0", CapabilityState.BOUNDED, "provenance_required_sensitive_redaction_no_mutation"),
    PlatformCapability("data_workspace", "0.36.0", CapabilityState.BOUNDED, "bounded_profile_no_raw_export_or_mutation"),
    PlatformCapability("code_repository", "0.37.0", CapabilityState.BOUNDED, "static_impact_analysis_no_execution_or_repository_write"),
    PlatformCapability("research_orchestration", "0.38.0", CapabilityState.BOUNDED, "supplied_sources_only_no_external_fetch"),
    PlatformCapability("business_operations", "0.39.0", CapabilityState.BOUNDED, "kpi_analysis_only_no_business_side_effects"),
    PlatformCapability("financial_planning", "0.40.0", CapabilityState.BOUNDED, "scenario_math_only_no_transactions_or_personalized_trades"),
    PlatformCapability("compliance_policy", "0.41.0", CapabilityState.BOUNDED, "evidence_gap_analysis_only_no_certification_or_policy_change"),
    PlatformCapability("incident_triage", "0.42.0", CapabilityState.BOUNDED, "ranking_only_no_remediation_restart_or_notification"),
    PlatformCapability("resource_capacity", "0.43.0", CapabilityState.BOUNDED, "analysis_only_no_provisioning_hiring_purchase_or_reallocation"),
    PlatformCapability("change_impact", "0.44.0", CapabilityState.BOUNDED, "dependency_analysis_only_no_code_config_migration_or_deployment"),
    PlatformCapability("experiment_causal", "0.45.0", CapabilityState.BOUNDED, "analysis_only_no_experiment_launch_randomization_or_enrollment"),
)


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = str(value).strip().split(".")
    if len(parts) != 3:
        raise ValueError("version_must_have_three_parts")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def build_platform_manifest(
    *,
    version: str = "0.45.0",
    capabilities: Sequence[PlatformCapability] = _DEFAULT_CAPABILITIES,
) -> PlatformManifest:
    current = _version_tuple(version)
    ordered = tuple(sorted(capabilities, key=lambda item: (_version_tuple(item.introduced_version), item.capability_id)))
    introduced = {item.introduced_version for item in ordered if _version_tuple(item.introduced_version) <= current}
    sequence_complete = all(item in introduced for item in _REQUIRED_SEQUENCE)

    by_id = {item.capability_id: item for item in ordered}
    required_disabled = (
        "raw_audio_capture",
        "raw_image_inference",
        "unrestricted_computer_execution",
        "arbitrary_shell_execution",
        "real_person_identity_recognition",
        "autonomous_security_policy_rewrite",
    )
    invariants = all(
        by_id.get(capability_id) is not None
        and by_id[capability_id].state == CapabilityState.DISABLED
        for capability_id in required_disabled
    )

    return PlatformManifest(
        version=version,
        capabilities=ordered,
        sequence_complete=sequence_complete,
        required_disabled_invariants_hold=invariants,
    )


def public_platform_manifest(manifest: PlatformManifest) -> dict[str, object]:
    return {
        "version": manifest.version,
        "sequence_complete": manifest.sequence_complete,
        "required_disabled_invariants_hold": manifest.required_disabled_invariants_hold,
        "capability_count": len(manifest.capabilities),
        "capabilities": [
            {
                "capability_id": item.capability_id,
                "introduced_version": item.introduced_version,
                "state": item.state.value,
                "safety_boundary": item.safety_boundary,
            }
            for item in manifest.capabilities
        ],
    }
