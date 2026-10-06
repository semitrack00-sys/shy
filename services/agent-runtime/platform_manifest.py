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
    "0.46.0",
    "0.47.0",
    "0.48.0",
    "0.49.0",
    "0.50.0",
    "0.51.0",
    "0.52.0",
    "0.53.0",
    "0.54.0",
    "0.55.0",
    "0.56.0",
    "0.57.0",
    "0.58.0",
    "0.59.0",
    "0.60.0",
    "0.61.0",
    "0.62.0",
    "0.63.0",
    "0.64.0",
    "0.65.0",
    "0.66.0",
    "0.67.0",
    "0.68.0",
    "0.69.0",
    "0.70.0",
    "0.71.0",
    "0.72.0",
    "0.73.0",
    "0.74.0",
    "0.75.0",
    "0.76.0",
    "0.77.0",
    "0.78.0",
    "0.79.0",
    "0.80.0",
    "0.81.0",
    "0.82.0",
    "0.83.0",
    "0.84.0",
    "0.85.0",
    "0.86.0",
    "0.87.0",
    "0.88.0",
    "0.89.0",
    "0.90.0",
    "0.91.0",
    "0.92.0",
    "0.93.0",
    "0.94.0",
    "0.95.0",
    "0.96.0",
    "0.97.0",
    "0.98.0",
    "0.99.0",
    "0.100.0",
    "0.101.0",
    "0.102.0",
    "0.103.0",
    "0.104.0",
    "0.105.0",
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
    PlatformCapability("raw_audio_capture", "0.30.0", CapabilityState.DISABLED, "core_audio_provider_not_connected_browser_capture_is_separate"),
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
    PlatformCapability("forecast_trend", "0.46.0", CapabilityState.BOUNDED, "supplied_series_projection_only_no_external_fetch_or_transactions"),
    PlatformCapability("approval_governance", "0.47.0", CapabilityState.BOUNDED, "verified_human_quorum_only_no_self_approval_tokens_permissions_or_execution"),
    PlatformCapability("resilience_fallback", "0.48.0", CapabilityState.BOUNDED, "planning_only_no_failover_traffic_switch_restart_or_config_change"),
    PlatformCapability("release_readiness", "0.49.0", CapabilityState.BOUNDED, "evaluation_only_no_deploy_publish_merge_or_promotion"),
    PlatformCapability("integrated_platform_v050", "0.50.0", CapabilityState.BOUNDED, "coordination_and_readiness_only_protected_disabled_invariants_preserved"),
    PlatformCapability("chunk_text", "0.51.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("rank_passages", "0.52.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("fuse_rankings", "0.53.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("pack_context", "0.54.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("validate_citations", "0.55.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("detect_conflicts", "0.56.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("source_freshness", "0.57.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("consolidate_memory", "0.58.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("redact_text", "0.59.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("answerability", "0.60.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("schedule_tasks", "0.61.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("critical_path", "0.62.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("verify_checkpoint", "0.63.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("retry_policy", "0.64.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("idempotency_fingerprint", "0.65.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("allocate_budget", "0.66.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("cancellation_plan", "0.67.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("approval_binding", "0.68.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("recovery_plan", "0.69.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("dry_run", "0.70.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("profile_schema", "0.71.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("descriptive_stats", "0.72.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("detect_outliers", "0.73.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("missing_report", "0.74.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("deduplicate_rows", "0.75.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("join_rows", "0.76.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("aggregate_rows", "0.77.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("transform_rows", "0.78.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("compare_snapshots", "0.79.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("data_quality", "0.80.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("injection_scan", "0.81.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("url_policy", "0.82.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("path_policy", "0.83.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("permission_diff", "0.84.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("tool_contract", "0.85.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("audit_chain", "0.86.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("config_check", "0.87.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("dependency_lock", "0.88.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("backup_verify", "0.89.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("provenance_trace", "0.90.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("health_summary", "0.91.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("slo_report", "0.92.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("latency_report", "0.93.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("cluster_errors", "0.94.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("capacity_estimate", "0.95.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("regression_report", "0.96.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("evaluation_scorecard", "0.97.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("release_gate", "0.98.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("compatibility_report", "0.99.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("evidence_pipeline", "0.100.0", CapabilityState.BOUNDED, "supplied_data_only_no_external_execution_or_persistence"),
    PlatformCapability("browser_voice_chat", "0.101.0", CapabilityState.BOUNDED, "browser_support_microphone_permission_and_transcript_review_required"),
    PlatformCapability("voice_interruption", "0.102.0", CapabilityState.BOUNDED, "client_playback_and_capture_cancel_only_no_server_task_cancellation"),
    PlatformCapability("voice_silence_handling", "0.103.0", CapabilityState.BOUNDED, "browser_speech_end_events_and_30_second_capture_limit"),
    PlatformCapability("local_microphone_input", "0.104.0", CapabilityState.BOUNDED, "selected_client_microphone_bounded_wav_configured_local_provider_required"),
    PlatformCapability("voice_output_controls", "0.105.0", CapabilityState.BOUNDED, "browser_voice_rate_volume_controls_installed_voices_required"),
    PlatformCapability("conversation_summary", "0.105.1", CapabilityState.BOUNDED, "browser_local_bounded_excerpts_no_generated_facts_or_completion_inference"),
    PlatformCapability("reviewed_memory_controls", "0.105.1", CapabilityState.BOUNDED, "existing_local_user_explicit_confirmation_revision_check_no_multiuser_authentication"),
    PlatformCapability("project_memory_scopes", "0.105.4", CapabilityState.BOUNDED, "separate_local_project_conversations_durable_memories_and_save_preferences_not_authenticated_multi_user_access"),
    PlatformCapability("automatic_memory_save_controls", "0.105.3", CapabilityState.BOUNDED, "confirmed_persistent_local_user_pause_resume_legacy_default_enabled_existing_retrieval_and_chat_history_unchanged"),
    PlatformCapability("ordinary_chat_context_budget", "0.105.2", CapabilityState.BOUNDED, "hard_character_and_message_budgets_including_fallback_not_unlimited_context_or_token_guarantee"),
)


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = str(value).strip().split(".")
    if len(parts) != 3:
        raise ValueError("version_must_have_three_parts")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def build_platform_manifest(
    *,
    version: str = "0.105.4",
    capabilities: Sequence[PlatformCapability] = _DEFAULT_CAPABILITIES,
) -> PlatformManifest:
    current = _version_tuple(version)
    ordered = tuple(sorted((item for item in capabilities if _version_tuple(item.introduced_version) <= current), key=lambda item: (_version_tuple(item.introduced_version), item.capability_id)))
    introduced = {item.introduced_version for item in ordered if _version_tuple(item.introduced_version) <= current}
    required_through_current = tuple(
        item for item in _REQUIRED_SEQUENCE
        if _version_tuple(item) <= current
    )
    sequence_complete = all(item in introduced for item in required_through_current)

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
