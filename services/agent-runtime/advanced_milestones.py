from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AdvancedBoundary(str, Enum):
    READY = "READY"
    INVALID_INPUT = "INVALID_INPUT"
    DATA_REQUIRED = "DATA_REQUIRED"
    PROTECTED_TARGET = "PROTECTED_TARGET"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class AdvancedResult:
    capability: str
    boundary: AdvancedBoundary
    reason: str
    payload: dict[str, object]
    side_effect_performed: bool


_PROTECTED_RECOVERY_MARKERS = (
    "security policy",
    "credentials",
    "password",
    "private key",
    "authentication",
    "authorization",
    "permission store",
)


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _recovery_rollback(payload: Mapping[str, object]) -> AdvancedResult:
    target = str(payload.get("target_checkpoint") or "").strip()
    raw_checkpoints = payload.get("checkpoints") or []

    if not isinstance(raw_checkpoints, list):
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.INVALID_INPUT,
            "checkpoints_must_be_a_list",
            {},
            False,
        )

    checkpoints: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in raw_checkpoints[:64]:
        if not isinstance(raw, dict):
            continue
        checkpoint_id = str(raw.get("checkpoint_id") or "").strip()
        if not checkpoint_id or checkpoint_id in seen:
            return AdvancedResult(
                "recovery_rollback",
                AdvancedBoundary.INVALID_INPUT,
                "checkpoint_ids_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(checkpoint_id)
        checkpoints.append(
            {
                "checkpoint_id": checkpoint_id,
                "verified": bool(raw.get("verified", False)),
                "description": str(raw.get("description") or "").strip()[:500],
            }
        )

    if not target:
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.DATA_REQUIRED,
            "target_checkpoint_required",
            {"checkpoint_count": len(checkpoints)},
            False,
        )

    protected_text = _norm(payload.get("target_resource")) + " " + _norm(payload.get("objective"))
    if any(marker in protected_text for marker in _PROTECTED_RECOVERY_MARKERS):
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.PROTECTED_TARGET,
            "protected_security_or_credential_target",
            {"target_checkpoint": target},
            False,
        )

    selected = next((item for item in checkpoints if item["checkpoint_id"] == target), None)
    if selected is None:
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.DATA_REQUIRED,
            "target_checkpoint_not_found",
            {"target_checkpoint": target, "checkpoint_count": len(checkpoints)},
            False,
        )

    if not bool(selected["verified"]):
        return AdvancedResult(
            "recovery_rollback",
            AdvancedBoundary.CONFLICT,
            "verified_checkpoint_required",
            {"target_checkpoint": target, "verified": False},
            False,
        )

    return AdvancedResult(
        "recovery_rollback",
        AdvancedBoundary.READY,
        "rollback_plan_ready",
        {
            "target_checkpoint": target,
            "verified": True,
            "plan_steps": [
                "capture_current_state",
                "verify_target_checkpoint",
                "request_execution_approval",
                "execute_via_authorized_runtime_only",
                "verify_post_recovery_state",
            ],
            "execution_allowed_here": False,
        },
        False,
    )


_SENSITIVE_DOCUMENT_MARKERS = (
    "password",
    "api key",
    "secret",
    "social security",
    "ssn",
    "credit card",
    "bank account",
    "private key",
)


def _document_intelligence(payload: Mapping[str, object]) -> AdvancedResult:
    source_id = str(payload.get("source_id") or "").strip()
    raw_sections = payload.get("sections") or []
    max_sections = max(1, min(int(payload.get("max_sections") or 64), 128))

    if not source_id:
        return AdvancedResult(
            "document_intelligence",
            AdvancedBoundary.DATA_REQUIRED,
            "source_id_required",
            {},
            False,
        )
    if not isinstance(raw_sections, list):
        return AdvancedResult(
            "document_intelligence",
            AdvancedBoundary.INVALID_INPUT,
            "sections_must_be_a_list",
            {"source_id": source_id},
            False,
        )

    selected = raw_sections[:max_sections]
    if not selected:
        return AdvancedResult(
            "document_intelligence",
            AdvancedBoundary.DATA_REQUIRED,
            "document_sections_required",
            {"source_id": source_id},
            False,
        )

    seen: set[str] = set()
    pages: set[int] = set()
    sensitive = False
    citation_ids: list[str] = []

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "document_intelligence",
                AdvancedBoundary.INVALID_INPUT,
                "section_must_be_an_object",
                {"source_id": source_id},
                False,
            )

        section_id = str(raw.get("section_id") or "").strip()
        if not section_id or section_id in seen:
            return AdvancedResult(
                "document_intelligence",
                AdvancedBoundary.INVALID_INPUT,
                "section_ids_must_be_unique_and_nonempty",
                {"source_id": source_id},
                False,
            )
        seen.add(section_id)

        if not bool(raw.get("provenance_available", False)):
            return AdvancedResult(
                "document_intelligence",
                AdvancedBoundary.DATA_REQUIRED,
                "section_provenance_required",
                {"source_id": source_id, "section_id": section_id},
                False,
            )

        page = int(raw.get("page") or 0)
        if page <= 0:
            return AdvancedResult(
                "document_intelligence",
                AdvancedBoundary.INVALID_INPUT,
                "positive_page_number_required",
                {"source_id": source_id, "section_id": section_id},
                False,
            )
        pages.add(page)

        text = _norm(raw.get("text"))
        if any(marker in text for marker in _SENSITIVE_DOCUMENT_MARKERS):
            sensitive = True

        citation_ids.append(f"{source_id}:{section_id}")

    return AdvancedResult(
        "document_intelligence",
        AdvancedBoundary.READY,
        "document_metadata_ready",
        {
            "source_id": source_id,
            "section_count": len(selected),
            "page_count": len(pages),
            "citation_ids": citation_ids,
            "citations_supported": True,
            "sensitive_content_detected": sensitive,
            "redaction_required": sensitive,
            "raw_text_returned": False,
            "section_limit_enforced": len(raw_sections) <= max_sections,
        },
        False,
    )


def _data_workspace(payload: Mapping[str, object]) -> AdvancedResult:
    raw_columns = payload.get("columns") or []
    raw_rows = payload.get("rows") or []
    max_rows = max(1, min(int(payload.get("max_rows") or 500), 2000))

    if not isinstance(raw_columns, list) or not raw_columns:
        return AdvancedResult(
            "data_workspace",
            AdvancedBoundary.DATA_REQUIRED,
            "columns_required",
            {},
            False,
        )
    if not isinstance(raw_rows, list):
        return AdvancedResult(
            "data_workspace",
            AdvancedBoundary.INVALID_INPUT,
            "rows_must_be_a_list",
            {},
            False,
        )

    columns: list[str] = []
    seen: set[str] = set()
    for raw in raw_columns[:256]:
        name = str(raw.get("name") if isinstance(raw, dict) else raw).strip()
        if not name or name in seen:
            return AdvancedResult(
                "data_workspace",
                AdvancedBoundary.INVALID_INPUT,
                "column_names_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(name)
        columns.append(name)

    selected_rows = raw_rows[:max_rows]
    missing_counts = {name: 0 for name in columns}
    observed_cells = 0
    for raw in selected_rows:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "data_workspace",
                AdvancedBoundary.INVALID_INPUT,
                "rows_must_be_objects",
                {"row_count": len(selected_rows)},
                False,
            )
        for name in columns:
            observed_cells += 1
            value = raw.get(name)
            if value is None or value == "":
                missing_counts[name] += 1

    row_count = len(selected_rows)
    missing_rates = {
        name: round((missing_counts[name] / row_count), 6) if row_count else 0.0
        for name in columns
    }

    return AdvancedResult(
        "data_workspace",
        AdvancedBoundary.READY,
        "data_profile_ready",
        {
            "column_count": len(columns),
            "row_count_profiled": row_count,
            "missing_rates": missing_rates,
            "sample_limit_enforced": len(raw_rows) <= max_rows,
            "raw_rows_returned": False,
            "dataset_mutated": False,
            "query_executed": False,
            "observed_cells": observed_cells,
        },
        False,
    )


def _safe_repo_path(value: object) -> str | None:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or (len(raw) > 2 and raw[1] == ":"):
        return None
    parts = [part for part in raw.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def _code_repository(payload: Mapping[str, object]) -> AdvancedResult:
    raw_files = payload.get("files") or []
    raw_changed = payload.get("changed_paths") or []
    max_files = max(1, min(int(payload.get("max_files") or 300), 1000))
    max_impacted = max(1, min(int(payload.get("max_impacted") or 100), 300))

    if not isinstance(raw_files, list) or not raw_files:
        return AdvancedResult(
            "code_repository",
            AdvancedBoundary.DATA_REQUIRED,
            "repository_files_required",
            {},
            False,
        )
    if not isinstance(raw_changed, list):
        return AdvancedResult(
            "code_repository",
            AdvancedBoundary.INVALID_INPUT,
            "changed_paths_must_be_a_list",
            {},
            False,
        )

    selected = raw_files[:max_files]
    graph: dict[str, tuple[str, ...]] = {}
    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.INVALID_INPUT,
                "file_entries_must_be_objects",
                {},
                False,
            )
        path = _safe_repo_path(raw.get("path"))
        if path is None or path in graph:
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.PROTECTED_TARGET,
                "unsafe_or_duplicate_repository_path",
                {},
                False,
            )

        raw_deps = raw.get("dependencies") or []
        if not isinstance(raw_deps, list):
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.INVALID_INPUT,
                "dependencies_must_be_a_list",
                {"path": path},
                False,
            )
        deps: list[str] = []
        for dep in raw_deps[:128]:
            safe = _safe_repo_path(dep)
            if safe is None:
                return AdvancedResult(
                    "code_repository",
                    AdvancedBoundary.PROTECTED_TARGET,
                    "unsafe_dependency_path",
                    {"path": path},
                    False,
                )
            deps.append(safe)
        graph[path] = tuple(dict.fromkeys(deps))

    changed: list[str] = []
    for raw in raw_changed[:max_impacted]:
        safe = _safe_repo_path(raw)
        if safe is None:
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.PROTECTED_TARGET,
                "unsafe_changed_path",
                {},
                False,
            )
        if safe not in graph:
            return AdvancedResult(
                "code_repository",
                AdvancedBoundary.DATA_REQUIRED,
                "changed_path_not_in_repository_snapshot",
                {"changed_path": safe},
                False,
            )
        changed.append(safe)

    reverse: dict[str, set[str]] = {path: set() for path in graph}
    for path, deps in graph.items():
        for dep in deps:
            if dep in reverse:
                reverse[dep].add(path)

    impacted = set(changed)
    frontier = list(changed)
    while frontier and len(impacted) < max_impacted:
        current = frontier.pop(0)
        for dependent in sorted(reverse.get(current, ())):
            if dependent not in impacted:
                impacted.add(dependent)
                frontier.append(dependent)
                if len(impacted) >= max_impacted:
                    break

    return AdvancedResult(
        "code_repository",
        AdvancedBoundary.READY,
        "repository_impact_analysis_ready",
        {
            "file_count_profiled": len(graph),
            "changed_paths": sorted(set(changed)),
            "impacted_paths": sorted(impacted),
            "file_limit_enforced": len(raw_files) <= max_files,
            "impact_limit_enforced": len(impacted) < max_impacted or not frontier,
            "raw_file_content_returned": False,
            "code_execution_performed": False,
            "repository_write_performed": False,
        },
        False,
    )


_RESEARCH_AUTHORITY = {
    "PRIMARY": 4,
    "AUTHORITATIVE": 3,
    "SECONDARY": 2,
    "COMMUNITY": 1,
    "UNKNOWN": 0,
}


def _research_orchestration(payload: Mapping[str, object]) -> AdvancedResult:
    raw_sources = payload.get("sources") or []
    current_required = bool(payload.get("current_required", False))
    max_sources = max(1, min(int(payload.get("max_sources") or 16), 64))
    max_age_days = max(0, min(int(payload.get("max_age_days") or 30), 3650))

    if not isinstance(raw_sources, list) or not raw_sources:
        return AdvancedResult(
            "research_orchestration",
            AdvancedBoundary.DATA_REQUIRED,
            "research_sources_required",
            {"external_fetch_performed": False},
            False,
        )

    ranked: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in raw_sources[:max_sources]:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "research_orchestration",
                AdvancedBoundary.INVALID_INPUT,
                "source_entries_must_be_objects",
                {"external_fetch_performed": False},
                False,
            )

        source_id = str(raw.get("source_id") or "").strip()
        if not source_id or source_id in seen:
            return AdvancedResult(
                "research_orchestration",
                AdvancedBoundary.INVALID_INPUT,
                "source_ids_must_be_unique_and_nonempty",
                {"external_fetch_performed": False},
                False,
            )
        seen.add(source_id)

        if not bool(raw.get("provenance_available", False)):
            return AdvancedResult(
                "research_orchestration",
                AdvancedBoundary.DATA_REQUIRED,
                "source_provenance_required",
                {"source_id": source_id, "external_fetch_performed": False},
                False,
            )

        authority = str(raw.get("authority") or "UNKNOWN").strip().upper()
        if authority not in _RESEARCH_AUTHORITY:
            authority = "UNKNOWN"

        age_days = int(raw.get("age_days") or 0)
        if age_days < 0:
            return AdvancedResult(
                "research_orchestration",
                AdvancedBoundary.INVALID_INPUT,
                "source_age_days_must_be_nonnegative",
                {"source_id": source_id, "external_fetch_performed": False},
                False,
            )

        ranked.append(
            {
                "source_id": source_id,
                "authority": authority,
                "authority_score": _RESEARCH_AUTHORITY[authority],
                "age_days": age_days,
                "fresh": age_days <= max_age_days,
                "claim": _norm(raw.get("claim")),
            }
        )

    ranked.sort(key=lambda item: (-int(item["authority_score"]), int(item["age_days"]), str(item["source_id"])))
    fresh = [item for item in ranked if bool(item["fresh"])]
    authoritative_count = sum(1 for item in ranked if int(item["authority_score"]) >= 3)
    claims = {str(item["claim"]) for item in ranked if str(item["claim"])}

    if current_required and not fresh:
        return AdvancedResult(
            "research_orchestration",
            AdvancedBoundary.DATA_REQUIRED,
            "fresh_current_sources_required",
            {
                "source_count": len(ranked),
                "fresh_source_count": 0,
                "authoritative_source_count": authoritative_count,
                "external_fetch_performed": False,
            },
            False,
        )

    boundary = AdvancedBoundary.CONFLICT if len(claims) > 1 else AdvancedBoundary.READY
    reason = "conflicting_source_claims" if boundary == AdvancedBoundary.CONFLICT else "research_plan_ready"

    return AdvancedResult(
        "research_orchestration",
        boundary,
        reason,
        {
            "selected_source_ids": [str(item["source_id"]) for item in ranked],
            "source_count": len(ranked),
            "fresh_source_count": len(fresh),
            "authoritative_source_count": authoritative_count,
            "current_required": current_required,
            "source_limit_enforced": len(raw_sources) <= max_sources,
            "external_fetch_performed": False,
            "source_content_returned": False,
        },
        False,
    )


def _business_operations(payload: Mapping[str, object]) -> AdvancedResult:
    raw_kpis = payload.get("kpis") or []
    max_kpis = max(1, min(int(payload.get("max_kpis") or 32), 128))

    if not isinstance(raw_kpis, list) or not raw_kpis:
        return AdvancedResult(
            "business_operations",
            AdvancedBoundary.DATA_REQUIRED,
            "business_kpis_required",
            {},
            False,
        )

    selected = raw_kpis[:max_kpis]
    scored: list[dict[str, object]] = []
    seen: set[str] = set()
    weight_total = 0.0
    weighted_score = 0.0

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "business_operations",
                AdvancedBoundary.INVALID_INPUT,
                "kpi_entries_must_be_objects",
                {},
                False,
            )

        name = str(raw.get("name") or "").strip()
        if not name or name in seen:
            return AdvancedResult(
                "business_operations",
                AdvancedBoundary.INVALID_INPUT,
                "kpi_names_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(name)

        value = float(raw.get("value") or 0.0)
        target = float(raw.get("target") or 0.0)
        weight = float(raw.get("weight") or 1.0)
        direction = str(raw.get("direction") or "HIGHER").strip().upper()

        if target <= 0 or weight < 0 or direction not in {"HIGHER", "LOWER"}:
            return AdvancedResult(
                "business_operations",
                AdvancedBoundary.INVALID_INPUT,
                "positive_target_nonnegative_weight_and_valid_direction_required",
                {"kpi": name},
                False,
            )

        if direction == "HIGHER":
            performance = max(0.0, min(1.0, value / target))
        else:
            performance = 1.0 if value <= target else max(0.0, min(1.0, target / value))

        weighted_score += performance * weight
        weight_total += weight
        scored.append(
            {
                "name": name,
                "performance": round(performance, 6),
                "on_target": performance >= 1.0,
                "bottleneck": performance < 0.8,
            }
        )

    if weight_total <= 0:
        return AdvancedResult(
            "business_operations",
            AdvancedBoundary.INVALID_INPUT,
            "positive_total_weight_required",
            {},
            False,
        )

    score = round(weighted_score / weight_total, 6)
    bottlenecks = [
        str(item["name"])
        for item in sorted(scored, key=lambda item: (float(item["performance"]), str(item["name"])))
        if bool(item["bottleneck"])
    ]

    return AdvancedResult(
        "business_operations",
        AdvancedBoundary.READY,
        "business_operations_assessment_ready",
        {
            "operations_score": score,
            "kpi_count": len(scored),
            "bottlenecks": bottlenecks,
            "focus_order": bottlenecks[:5],
            "kpi_limit_enforced": len(raw_kpis) <= max_kpis,
            "pricing_changed": False,
            "staff_dispatched": False,
            "money_spent": False,
            "business_action_executed": False,
        },
        False,
    )


def _financial_planning(payload: Mapping[str, object]) -> AdvancedResult:
    raw_scenarios = payload.get("scenarios") or []
    max_scenarios = max(1, min(int(payload.get("max_scenarios") or 12), 32))

    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        return AdvancedResult(
            "financial_planning",
            AdvancedBoundary.DATA_REQUIRED,
            "financial_scenarios_required",
            {},
            False,
        )

    selected = raw_scenarios[:max_scenarios]
    summaries: list[dict[str, object]] = []
    seen: set[str] = set()
    probability_total = 0.0

    for raw in selected:
        if not isinstance(raw, dict):
            return AdvancedResult(
                "financial_planning",
                AdvancedBoundary.INVALID_INPUT,
                "scenario_entries_must_be_objects",
                {},
                False,
            )

        name = str(raw.get("name") or "").strip()
        if not name or name in seen:
            return AdvancedResult(
                "financial_planning",
                AdvancedBoundary.INVALID_INPUT,
                "scenario_names_must_be_unique_and_nonempty",
                {},
                False,
            )
        seen.add(name)

        revenue = float(raw.get("revenue") or 0.0)
        costs = float(raw.get("costs") or 0.0)
        investment = float(raw.get("investment") or 0.0)
        probability = float(raw.get("probability") or 1.0)

        if min(revenue, costs, investment, probability) < 0:
            return AdvancedResult(
                "financial_planning",
                AdvancedBoundary.INVALID_INPUT,
                "financial_inputs_must_be_nonnegative",
                {"scenario": name},
                False,
            )

        operating_profit = revenue - costs
        net_after_investment = operating_profit - investment
        roi = (net_after_investment / investment) if investment > 0 else None
        margin = (operating_profit / revenue) if revenue > 0 else None
        break_even_revenue = costs + investment

        probability_total += probability
        summaries.append(
            {
                "name": name,
                "revenue": round(revenue, 2),
                "costs": round(costs, 2),
                "investment": round(investment, 2),
                "probability": probability,
                "operating_profit": round(operating_profit, 2),
                "net_after_investment": round(net_after_investment, 2),
                "roi": round(roi, 6) if roi is not None else None,
                "operating_margin": round(margin, 6) if margin is not None else None,
                "break_even_revenue": round(break_even_revenue, 2),
            }
        )

    if probability_total <= 0:
        return AdvancedResult(
            "financial_planning",
            AdvancedBoundary.INVALID_INPUT,
            "positive_probability_mass_required",
            {},
            False,
        )

    expected_net = sum(
        (float(item["probability"]) / probability_total) * float(item["net_after_investment"])
        for item in summaries
    )

    return AdvancedResult(
        "financial_planning",
        AdvancedBoundary.READY,
        "financial_scenario_analysis_ready",
        {
            "scenario_count": len(summaries),
            "scenarios": summaries,
            "expected_net_after_investment": round(expected_net, 2),
            "scenario_limit_enforced": len(raw_scenarios) <= max_scenarios,
            "decision_support_only": True,
            "transaction_executed": False,
            "personalized_buy_sell_instruction": False,
        },
        False,
    )


_EVALUATORS = {
    "recovery_rollback": _recovery_rollback,
    "document_intelligence": _document_intelligence,
    "data_workspace": _data_workspace,
    "code_repository": _code_repository,
    "research_orchestration": _research_orchestration,
    "business_operations": _business_operations,
    "financial_planning": _financial_planning,
}


def available_advanced_capabilities() -> tuple[str, ...]:
    return tuple(sorted(_EVALUATORS))


def evaluate_advanced_capability(
    capability: str,
    payload: Mapping[str, object],
) -> AdvancedResult:
    key = _norm(capability).replace(" ", "_")
    evaluator = _EVALUATORS.get(key)
    if evaluator is None:
        return AdvancedResult(
            key,
            AdvancedBoundary.INVALID_INPUT,
            "unsupported_advanced_capability",
            {"available_capabilities": list(available_advanced_capabilities())},
            False,
        )
    return evaluator(payload)


def public_advanced_result(result: AdvancedResult) -> dict[str, object]:
    return {
        "capability": result.capability,
        "boundary": result.boundary.value,
        "reason": result.reason,
        "payload": dict(result.payload),
        "side_effect_performed": result.side_effect_performed,
    }
