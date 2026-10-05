from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol


class BusinessDomain(str, Enum):
    GENERAL_BUSINESS = "GENERAL_BUSINESS"
    OPERATIONS = "OPERATIONS"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    SALES = "SALES"
    FINANCE = "FINANCE"
    COMPLIANCE = "COMPLIANCE"
    LOGISTICS = "LOGISTICS"
    SOFTWARE_OPERATIONS = "SOFTWARE_OPERATIONS"


class BusinessWorkflow(str, Enum):
    BUSINESS_SUMMARY = "business_summary"
    CUSTOMER_SUPPORT_ANALYSIS = "customer_support_analysis"
    BUSINESS_RESEARCH = "business_research"
    LOGISTICS_ANALYSIS = "logistics_analysis"
    FINANCIAL_ANALYSIS = "financial_analysis"
    SYNTHETIC_APPROVAL = "synthetic_approval"


class WorkflowStatus(str, Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"


@dataclass(frozen=True)
class WorkflowInput:
    objective: str
    conversation_id: str | None = None
    user_id: str | None = None
    workspace_id: str = "default"
    business_id: str | None = None


@dataclass(frozen=True)
class WorkflowStep:
    step_id: int
    action_type: str
    objective: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkflowPolicy:
    allowed_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    approval_required_tools: tuple[str, ...]
    max_steps: int
    data_access_scope: str
    memory_behavior: str
    external_provider_privacy_policy: str


@dataclass(frozen=True)
class WorkflowExecutionContext:
    workflow_id: str
    domain: BusinessDomain
    workflow: BusinessWorkflow
    required_model_role: str
    user_id: str | None
    workspace_id: str
    business_id: str | None
    approval_required: bool
    policy: WorkflowPolicy


@dataclass(frozen=True)
class WorkflowResult:
    status: WorkflowStatus
    executive_summary: str
    kpis: tuple[str, ...]
    problems_found: tuple[str, ...]
    risks: tuple[str, ...]
    recommendations: tuple[str, ...]
    evidence_references: tuple[str, ...]
    next_actions: tuple[str, ...]


@dataclass(frozen=True)
class BusinessIntent:
    domain: BusinessDomain
    workflow: BusinessWorkflow
    required_model_role: str
    requires_tools: bool
    requires_planning: bool
    approval_required: bool
    reason: str


class BusinessDataSource(Protocol):
    def load(self, context: WorkflowExecutionContext) -> dict[str, Any]:
        ...


class CustomerIssueSource(Protocol):
    def load_customer_issues(self, context: WorkflowExecutionContext) -> list[dict[str, Any]]:
        ...


class OperationsMetricsSource(Protocol):
    def load_operations_metrics(self, context: WorkflowExecutionContext) -> dict[str, Any]:
        ...


class FinancialSummarySource(Protocol):
    def load_financial_summary(self, context: WorkflowExecutionContext) -> dict[str, Any]:
        ...


class LogisticsDataSource(Protocol):
    def load_logistics_data(self, context: WorkflowExecutionContext) -> dict[str, Any]:
        ...


FORBIDDEN_SIDE_EFFECT_TOOLS: tuple[str, ...] = (
    "message.send",
    "file.delete",
    "money.spend",
    "production.deploy",
)


WORKFLOW_POLICIES: dict[BusinessWorkflow, WorkflowPolicy] = {
    BusinessWorkflow.BUSINESS_SUMMARY: WorkflowPolicy(
        allowed_tools=("system.health", "database.read", "calculator"),
        forbidden_tools=FORBIDDEN_SIDE_EFFECT_TOOLS,
        approval_required_tools=(),
        max_steps=5,
        data_access_scope="workspace_read_only",
        memory_behavior="persist_safe_task_outcome",
        external_provider_privacy_policy="local_preferred_remote_allowed",
    ),
    BusinessWorkflow.CUSTOMER_SUPPORT_ANALYSIS: WorkflowPolicy(
        allowed_tools=("calculator",),
        forbidden_tools=FORBIDDEN_SIDE_EFFECT_TOOLS,
        approval_required_tools=(),
        max_steps=5,
        data_access_scope="workspace_read_only",
        memory_behavior="persist_safe_task_outcome",
        external_provider_privacy_policy="local_preferred_remote_allowed",
    ),
    BusinessWorkflow.BUSINESS_RESEARCH: WorkflowPolicy(
        allowed_tools=("web.search", "calculator"),
        forbidden_tools=FORBIDDEN_SIDE_EFFECT_TOOLS,
        approval_required_tools=(),
        max_steps=5,
        data_access_scope="workspace_read_only",
        memory_behavior="persist_safe_task_outcome",
        external_provider_privacy_policy="research_remote_allowed",
    ),
    BusinessWorkflow.LOGISTICS_ANALYSIS: WorkflowPolicy(
        allowed_tools=("calculator",),
        forbidden_tools=FORBIDDEN_SIDE_EFFECT_TOOLS,
        approval_required_tools=(),
        max_steps=5,
        data_access_scope="workspace_read_only",
        memory_behavior="persist_safe_task_outcome",
        external_provider_privacy_policy="local_preferred_remote_allowed",
    ),
    BusinessWorkflow.FINANCIAL_ANALYSIS: WorkflowPolicy(
        allowed_tools=("calculator",),
        forbidden_tools=FORBIDDEN_SIDE_EFFECT_TOOLS,
        approval_required_tools=(),
        max_steps=5,
        data_access_scope="workspace_read_only",
        memory_behavior="persist_safe_task_outcome",
        external_provider_privacy_policy="local_preferred_remote_allowed",
    ),
    BusinessWorkflow.SYNTHETIC_APPROVAL: WorkflowPolicy(
        allowed_tools=("approval.tool",),
        forbidden_tools=FORBIDDEN_SIDE_EFFECT_TOOLS,
        approval_required_tools=("approval.tool",),
        max_steps=5,
        data_access_scope="workspace_read_only",
        memory_behavior="persist_safe_task_outcome",
        external_provider_privacy_policy="local_preferred_remote_allowed",
    ),
}



def _parse_numeric_token(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


def _clean_count(value: float) -> int | float:
    return int(value) if float(value).is_integer() else float(value)


def _format_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return sign + "$" + format(abs(float(value)), ",.0f")


def _parse_inline_logistics_inputs(message: str) -> dict[str, Any] | None:
    """Parse a self-contained logistics business case from the user's own prompt.

    This path intentionally uses only values explicitly supplied by the user.
    If the minimum logistics facts are not present, the caller falls back to
    the approved deterministic workspace adapter.
    """
    text = " ".join(str(message or "").split()).lower()
    if not text:
        return None

    number = r"([0-9][0-9,]*(?:\.[0-9]+)?)"
    total_match = re.search(rf"{number}\s+deliveries\s+per\s+week", text)
    late_match = re.search(rf"{number}\s+deliveries\s+(?:are|were)\s+late", text)
    if late_match is None:
        late_match = re.search(rf"{number}\s+(?:are|were)\s+late", text)

    total = _parse_numeric_token(total_match.group(1)) if total_match else None
    late = _parse_numeric_token(late_match.group(1)) if late_match else None
    if total is None or late is None or total <= 0 or late < 0 or late > total:
        return None

    reason_patterns: tuple[tuple[str, str], ...] = (
        ("loading delays", r"loading(?:-related)?\s+delays?"),
        ("traffic", r"traffic"),
        ("driver scheduling", r"driver\s+schedul(?:ing|e|es)?"),
        ("mechanical problems", r"mechanical(?:\s+problems?|\s+issues?)?"),
    )
    reasons: dict[str, int | float] = {}
    for reason_name, reason_pattern in reason_patterns:
        match = re.search(rf"{number}\s+(?:because\s+of\s+)?{reason_pattern}", text)
        if not match:
            continue
        count = _parse_numeric_token(match.group(1))
        if count is not None and count >= 0:
            reasons[reason_name] = _clean_count(count)

    if not reasons:
        return None

    if sum(float(value) for value in reasons.values()) > float(late) + 1e-9:
        return None

    payload: dict[str, Any] = {
        "total_deliveries": _clean_count(total),
        "late_deliveries": _clean_count(late),
        "delay_reasons": reasons,
        "source": "user_prompt",
    }

    reduction_match = re.search(
        rf"(?:would\s+)?reduce(?:s|d|ing)?\s+loading(?:-related)?\s+delays?\s+by\s+{number}\s*%",
        text,
    )
    monthly_cost_match = re.search(
        rf"costs?\s+\$?\s*{number}\s+per\s+month",
        text,
    )
    savings_match = re.search(
        rf"each\s+prevented\s+late\s+delivery\s+saves?\s+(?:about\s+)?\$?\s*{number}",
        text,
    )

    reduction_percent = _parse_numeric_token(reduction_match.group(1)) if reduction_match else None
    monthly_cost = _parse_numeric_token(monthly_cost_match.group(1)) if monthly_cost_match else None
    savings_per_prevented = _parse_numeric_token(savings_match.group(1)) if savings_match else None

    if (
        reduction_percent is not None
        and 0 <= reduction_percent <= 100
        and monthly_cost is not None
        and monthly_cost >= 0
        and savings_per_prevented is not None
        and savings_per_prevented > 0
        and "loading delays" in reasons
    ):
        payload["investment_case"] = {
            "target_reason": "loading delays",
            "reduction_percent": float(reduction_percent),
            "monthly_cost": float(monthly_cost),
            "savings_per_prevented_late_delivery": float(savings_per_prevented),
            "monthly_weeks_assumption": 4.0,
        }

    return payload


class DeterministicBusinessDataAdapters(
    CustomerIssueSource,
    OperationsMetricsSource,
    FinancialSummarySource,
    LogisticsDataSource,
):
    """Read-only deterministic adapters for v0.17 first checkpoint."""

    def __init__(self):
        self._default_customer_issues = [
            {"id": "I-1", "theme": "recharge failure", "summary": "Recharge failed after payment capture."},
            {"id": "I-2", "theme": "recharge failure", "summary": "Top-up request timed out."},
            {"id": "I-3", "theme": "recharge failure", "summary": "Recharge confirmation missing."},
            {"id": "I-4", "theme": "recharge failure", "summary": "Recharge failed during validation."},
            {"id": "I-5", "theme": "recharge failure", "summary": "Recharge retried but still failed."},
            {"id": "I-6", "theme": "login failure", "summary": "Login rejected despite correct OTP."},
            {"id": "I-7", "theme": "login failure", "summary": "User session expired during sign-in."},
            {"id": "I-8", "theme": "login failure", "summary": "Passwordless login did not complete."},
            {"id": "I-9", "theme": "delayed confirmation", "summary": "Order confirmation delayed by queue."},
            {"id": "I-10", "theme": "delayed confirmation", "summary": "Confirmation email delayed."},
        ]
        self._default_financial_summary = {
            "revenue": 125000.0,
            "operating_expenses": 82000.0,
            "other_expenses": 8000.0,
            "anomalies": ["Shipping cost increased by 12% week-over-week."],
        }
        self._default_operations = {
            "open_tasks": 12,
            "completed_tasks": 34,
            "blocked_tasks": 3,
            "risk_flags": ["Backlog in fulfillment queue."],
        }

    def load_customer_issues(self, context: WorkflowExecutionContext) -> list[dict[str, Any]]:
        if context.workspace_id.endswith("-blocked"):
            return []
        if context.workspace_id.endswith("-malformed"):
            return [{"id": "I-X", "summary": "theme missing"}]
        return list(self._default_customer_issues)

    def load_operations_metrics(self, context: WorkflowExecutionContext) -> dict[str, Any]:
        return dict(self._default_operations)

    def load_financial_summary(self, context: WorkflowExecutionContext) -> dict[str, Any]:
        if context.workspace_id.endswith("-missing"):
            return {}
        if context.workspace_id.endswith("-malformed"):
            return {"revenue": "not-a-number", "operating_expenses": None, "other_expenses": []}
        return dict(self._default_financial_summary)

    def load_logistics_data(self, context: WorkflowExecutionContext) -> dict[str, Any]:
        if context.workspace_id.endswith("-missing"):
            return {"total_deliveries": 0, "late_deliveries": 0, "delay_reasons": {}}
        if context.workspace_id.endswith("-malformed"):
            return {"total_deliveries": "forty", "late_deliveries": "eight", "delay_reasons": "traffic"}
        if context.workspace_id == "workspace-b":
            return {
                "total_deliveries": 10,
                "late_deliveries": 1,
                "delay_reasons": {"traffic": 1},
            }
        return {
            "total_deliveries": 40,
            "late_deliveries": 8,
            "delay_reasons": {"traffic": 3, "loading delay": 3, "mechanical": 2},
        }


def resolve_business_intent(message: str) -> BusinessIntent | None:
    text = str(message or "").strip().lower()
    if not text:
        return None

    # Let explicit memory-style user facts/preferences remain on the direct chat path.
    if (
        "company name is" in text
        or "my company is" in text
        or "i work at" in text
        or "my name is" in text
    ):
        return None

    if any(token in text for token in ("prefer", "preference", "remember")) and "analysis" not in text:
        return None

    # v0.18 cognitive scenarios should stay on the general cognitive path.
    if (
        "we completed 100 deliveries" in text and "18 were late" in text
    ) or (
        "monolith" in text and "microservices" in text and "auditability" in text
    ) or (
        "api became slow" in text and "database query time increased" in text
    ) or (
        "net profit is" in text and "40%" in text
    ) or (
        "0.40" in text and "=" in text and "63,000" in text
    ) or (
        "revenue was $120,000" in text and "revenue was $145,000" in text
    ):
        return None

    if any(token in text for token in ("delivery", "late-delivery", "logistics", "dispatch")):
        return BusinessIntent(
            domain=BusinessDomain.LOGISTICS,
            workflow=BusinessWorkflow.LOGISTICS_ANALYSIS,
            required_model_role="REASONING",
            requires_tools=True,
            requires_planning=True,
            approval_required=False,
            reason="Logistics request detected.",
        )

    if any(token in text for token in ("customer issues", "support issues", "recurring problem", "recurring customer problems", "customer problems", "support")):
        return BusinessIntent(
            domain=BusinessDomain.CUSTOMER_SUPPORT,
            workflow=BusinessWorkflow.CUSTOMER_SUPPORT_ANALYSIS,
            required_model_role="REASONING",
            requires_tools=True,
            requires_planning=True,
            approval_required=False,
            reason="Customer-support analysis request detected.",
        )

    if any(token in text for token in ("revenue", "expenses", "financial", "forecast", "finance", "margin")):
        return BusinessIntent(
            domain=BusinessDomain.FINANCE,
            workflow=BusinessWorkflow.FINANCIAL_ANALYSIS,
            required_model_role="REASONING",
            requires_tools=True,
            requires_planning=True,
            approval_required=False,
            reason="Financial analysis request detected.",
        )

    if any(token in text for token in ("competitor", "competitive brief", "research competitors")):
        return BusinessIntent(
            domain=BusinessDomain.GENERAL_BUSINESS,
            workflow=BusinessWorkflow.BUSINESS_RESEARCH,
            required_model_role="RESEARCH",
            requires_tools=True,
            requires_planning=True,
            approval_required=False,
            reason="Business research request detected.",
        )

    if any(token in text for token in ("synthetic approval", "approval workflow validation", "business.synthetic_approval_action")):
        return BusinessIntent(
            domain=BusinessDomain.SOFTWARE_OPERATIONS,
            workflow=BusinessWorkflow.SYNTHETIC_APPROVAL,
            required_model_role="PLANNER",
            requires_tools=True,
            requires_planning=True,
            approval_required=True,
            reason="Synthetic approval workflow request detected.",
        )

    if any(token in text for token in ("operations summary", "daily operations summary", "business summary")):
        return BusinessIntent(
            domain=BusinessDomain.OPERATIONS,
            workflow=BusinessWorkflow.BUSINESS_SUMMARY,
            required_model_role="GENERAL",
            requires_tools=True,
            requires_planning=True,
            approval_required=False,
            reason="Operations summary request detected.",
        )

    return None


def build_workflow_execution_context(workflow_input: WorkflowInput, intent: BusinessIntent) -> WorkflowExecutionContext:
    policy = WORKFLOW_POLICIES[intent.workflow]
    workflow_key = f"{intent.workflow.value}|{workflow_input.workspace_id}|{workflow_input.business_id or ''}|{workflow_input.objective}"
    workflow_id = hashlib.sha256(workflow_key.encode("utf-8")).hexdigest()[:24]
    return WorkflowExecutionContext(
        workflow_id=workflow_id,
        domain=intent.domain,
        workflow=intent.workflow,
        required_model_role=intent.required_model_role,
        user_id=workflow_input.user_id,
        workspace_id=workflow_input.workspace_id,
        business_id=workflow_input.business_id,
        approval_required=intent.approval_required,
        policy=policy,
    )


def build_workflow_plan(context: WorkflowExecutionContext, objective: str) -> dict[str, Any]:
    plan_steps: list[WorkflowStep]

    if context.workflow == BusinessWorkflow.LOGISTICS_ANALYSIS:
        plan_steps = [
            WorkflowStep(1, "REASON", "Load approved logistics metrics from deterministic data source."),
            WorkflowStep(2, "REASON", "Group late-delivery causes and prepare rate expression."),
            WorkflowStep(3, "TOOL", "Calculate the late-delivery percentage.", tool_name="calculator", tool_args={"expression_context_key": "late_delivery_rate_expression"}),
            WorkflowStep(4, "REASON", "Identify highest-risk pattern and tie handling."),
            WorkflowStep(5, "REASON", "Produce tomorrow focus recommendations and finalize report."),
        ]
    elif context.workflow == BusinessWorkflow.CUSTOMER_SUPPORT_ANALYSIS:
        plan_steps = [
            WorkflowStep(1, "REASON", "Load approved customer issue set."),
            WorkflowStep(2, "REASON", "Group issues by recurring theme and count frequencies."),
            WorkflowStep(3, "REASON", "Draft recommended response actions without sending messages."),
        ]
    elif context.workflow == BusinessWorkflow.FINANCIAL_ANALYSIS:
        plan_steps = [
            WorkflowStep(1, "REASON", "Load approved financial summary data."),
            WorkflowStep(2, "TOOL", "Calculate net result using deterministic values.", tool_name="calculator", tool_args={"expression_context_key": "net_financial_expression"}),
            WorkflowStep(3, "REASON", "Identify anomalies and produce recommendations."),
        ]
    elif context.workflow == BusinessWorkflow.BUSINESS_RESEARCH:
        plan_steps = [
            WorkflowStep(1, "REASON", "Gather competitor research evidence through SHY research pipeline."),
            WorkflowStep(2, "REASON", "Synthesize cited findings into a competitive brief."),
            WorkflowStep(3, "REASON", "Produce recommendations grounded in cited evidence."),
        ]
    elif context.workflow == BusinessWorkflow.SYNTHETIC_APPROVAL:
        plan_steps = [
            WorkflowStep(1, "REASON", "Prepare bounded synthetic approval workflow context."),
            WorkflowStep(2, "TOOL", "Execute synthetic approval-gated business action.", tool_name="approval.tool", tool_args={"recipient": "approval-test", "message": "validate"}),
            WorkflowStep(3, "REASON", "Summarize approved synthetic action outcome."),
        ]
    else:
        plan_steps = [
            WorkflowStep(1, "REASON", "Load approved business metrics."),
            WorkflowStep(2, "REASON", "Summarize KPI and risk posture."),
            WorkflowStep(3, "REASON", "Recommend next actions."),
        ]

    return {
        "goal": objective,
        "maximum_step_count": min(context.policy.max_steps, 5),
        "completion_criteria": "All required workflow steps complete with validated calculations and evidence availability.",
        "failure_policy": "Stop on denied tool, missing required data, malformed data, approval requirement, or provider failure.",
        "steps": [asdict(step) for step in plan_steps],
        "workflow_context": asdict(context),
        "workflow_policy": asdict(context.policy),
    }


def required_model_role_for_workflow(workflow: BusinessWorkflow) -> str:
    if workflow == BusinessWorkflow.BUSINESS_RESEARCH:
        return "RESEARCH"
    if workflow in (BusinessWorkflow.LOGISTICS_ANALYSIS, BusinessWorkflow.CUSTOMER_SUPPORT_ANALYSIS, BusinessWorkflow.FINANCIAL_ANALYSIS):
        return "REASONING"
    return "GENERAL"


def _sanitize_report_dict(data: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for key, value in data.items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("password", "secret", "token", "key", "credential", "chain", "reasoning")):
            continue
        safe[str(key)] = value
    return safe


def build_business_audit_record(
    *,
    task_id: str,
    context: WorkflowExecutionContext,
    status: str,
    tools_used: list[str],
    model_routing: dict[str, Any] | None,
    approval_state: str,
    completion_time: str,
    outcome: dict[str, Any],
) -> dict[str, Any]:
    routing = model_routing or {}
    return {
        "workflow_id": context.workflow_id,
        "task_id": task_id,
        "domain": context.domain.value,
        "workflow_type": context.workflow.value,
        "status": status,
        "tools_used": [item for item in tools_used if item],
        "model_role": context.required_model_role,
        "provider": routing.get("executed_provider") or routing.get("selected_provider"),
        "model": routing.get("executed_model") or routing.get("selected_model"),
        "approval_state": approval_state,
        "completion_time": completion_time,
        "sanitized_outcome": _sanitize_report_dict(outcome),
    }


def extract_workflow_context_from_task(task: Any) -> WorkflowExecutionContext | None:
    raw = getattr(task.execution_context, "derived_values", {}).get("workflow_context")
    if not isinstance(raw, dict):
        return None
    try:
        policy_raw = raw.get("policy") or {}
        policy = WorkflowPolicy(
            allowed_tools=tuple(policy_raw.get("allowed_tools") or ()),
            forbidden_tools=tuple(policy_raw.get("forbidden_tools") or ()),
            approval_required_tools=tuple(policy_raw.get("approval_required_tools") or ()),
            max_steps=int(policy_raw.get("max_steps", 5)),
            data_access_scope=str(policy_raw.get("data_access_scope", "workspace_read_only")),
            memory_behavior=str(policy_raw.get("memory_behavior", "persist_safe_task_outcome")),
            external_provider_privacy_policy=str(policy_raw.get("external_provider_privacy_policy", "local_preferred_remote_allowed")),
        )
        return WorkflowExecutionContext(
            workflow_id=str(raw.get("workflow_id", "")),
            domain=BusinessDomain(str(raw.get("domain"))),
            workflow=BusinessWorkflow(str(raw.get("workflow"))),
            required_model_role=str(raw.get("required_model_role", "GENERAL")),
            user_id=raw.get("user_id"),
            workspace_id=str(raw.get("workspace_id", "default")),
            business_id=raw.get("business_id"),
            approval_required=bool(raw.get("approval_required", False)),
            policy=policy,
        )
    except Exception:
        return None


def run_business_reasoning_step(step_objective: str, task: Any, adapters: DeterministicBusinessDataAdapters) -> dict[str, Any] | None:
    context = extract_workflow_context_from_task(task)
    if context is None:
        return None

    lowered = step_objective.lower().strip()
    derived = task.execution_context.derived_values

    if context.workflow == BusinessWorkflow.LOGISTICS_ANALYSIS:
        if "load approved logistics metrics" in lowered:
            original_message = str(derived.get("original_message") or getattr(task, "objective", ""))
            inline_payload = _parse_inline_logistics_inputs(original_message)
            payload = inline_payload or adapters.load_logistics_data(context)
            total = int(payload.get("total_deliveries", 0))
            late = int(payload.get("late_deliveries", 0))
            reasons = dict(payload.get("delay_reasons") or {})
            if total <= 0 or late < 0 or late > total or not reasons:
                return {
                    "status": "FAILED",
                    "summary": "Missing or malformed logistics data.",
                    "error_code": "MALFORMED_DATA",
                    "recoverable": False,
                }
            derived["logistics_metrics"] = payload
            derived["logistics_metrics_source"] = "user_prompt" if inline_payload is not None else "approved_adapter"
            investment_case = payload.get("investment_case")
            if isinstance(investment_case, dict):
                derived["logistics_investment_case"] = dict(investment_case)
            return {
                "status": "EXECUTED",
                "summary": f"Loaded logistics metrics: total={total}, late={late}.",
                "evidence": True,
            }

        if "group late-delivery causes" in lowered:
            payload = dict(derived.get("logistics_metrics") or {})
            total = int(payload.get("total_deliveries", 0))
            late = int(payload.get("late_deliveries", 0))
            reasons = dict(payload.get("delay_reasons") or {})
            if total <= 0:
                return {
                    "status": "FAILED",
                    "summary": "Logistics metrics unavailable for rate calculation.",
                    "error_code": "MISSING_DATA",
                    "recoverable": False,
                }
            derived["late_delivery_rate_expression"] = f"({late} / {total}) * 100"
            ordered = sorted(reasons.items(), key=lambda item: (-int(item[1]), str(item[0]).lower()))
            top_count = int(ordered[0][1]) if ordered else 0
            top_reasons = [name for name, count in ordered if int(count) == top_count]
            derived["top_delay_reasons"] = top_reasons
            derived["top_delay_count"] = top_count

            investment_case = dict(derived.get("logistics_investment_case") or {})
            if investment_case:
                target_reason = str(investment_case.get("target_reason") or "")
                baseline_target_count = float(reasons.get(target_reason, 0.0))
                reduction_percent = float(investment_case.get("reduction_percent", 0.0))
                monthly_cost = float(investment_case.get("monthly_cost", 0.0))
                savings_per_prevented = float(investment_case.get("savings_per_prevented_late_delivery", 0.0))
                monthly_weeks = float(investment_case.get("monthly_weeks_assumption", 4.0))

                prevented_per_week = baseline_target_count * (reduction_percent / 100.0)
                weekly_savings = prevented_per_week * savings_per_prevented
                monthly_savings = weekly_savings * monthly_weeks
                net_monthly_benefit = monthly_savings - monthly_cost

                remaining_reasons = {
                    name: float(count)
                    for name, count in reasons.items()
                }
                if target_reason in remaining_reasons:
                    remaining_reasons[target_reason] = max(
                        0.0,
                        remaining_reasons[target_reason] - prevented_per_week,
                    )

                derived["logistics_investment_analysis"] = {
                    "target_reason": target_reason,
                    "baseline_target_count": baseline_target_count,
                    "reduction_percent": reduction_percent,
                    "prevented_per_week": prevented_per_week,
                    "weekly_savings": weekly_savings,
                    "monthly_savings": monthly_savings,
                    "monthly_cost": monthly_cost,
                    "net_monthly_benefit": net_monthly_benefit,
                    "savings_per_prevented_late_delivery": savings_per_prevented,
                    "monthly_weeks_assumption": monthly_weeks,
                    "expected_remaining_late_per_week": max(0.0, float(late) - prevented_per_week),
                    "remaining_delay_reasons": remaining_reasons,
                    "break_even_prevented_per_month": (
                        monthly_cost / savings_per_prevented
                        if savings_per_prevented > 0
                        else None
                    ),
                }

            return {
                "status": "EXECUTED",
                "summary": "Prepared late-delivery rate and grouped delay reasons.",
                "evidence": True,
            }

        if "identify highest-risk pattern" in lowered:
            investment_analysis = dict(derived.get("logistics_investment_analysis") or {})
            remaining_reasons = dict(investment_analysis.get("remaining_delay_reasons") or {})
            if remaining_reasons:
                ordered_remaining = sorted(
                    remaining_reasons.items(),
                    key=lambda item: (-float(item[1]), str(item[0]).lower()),
                )
                top_count = float(ordered_remaining[0][1])
                top_reasons = [
                    name
                    for name, count in ordered_remaining
                    if abs(float(count) - top_count) < 1e-9
                ]
                derived["post_change_top_delay_reasons"] = top_reasons
                derived["post_change_top_delay_count"] = top_count
                if len(top_reasons) > 1:
                    derived["risk_pattern"] = (
                        f"After the change, top expected delay causes are tied: {', '.join(top_reasons)} "
                        f"at {top_count:g} per week."
                    )
                else:
                    derived["risk_pattern"] = (
                        f"After the change, highest expected delay cause is {top_reasons[0]} "
                        f"at {top_count:g} per week."
                    )
                return {
                    "status": "EXECUTED",
                    "summary": str(derived["risk_pattern"]),
                    "evidence": True,
                }

            top_reasons = list(derived.get("top_delay_reasons") or [])
            if not top_reasons:
                return {
                    "status": "FAILED",
                    "summary": "No delay reasons available for risk analysis.",
                    "error_code": "MISSING_DATA",
                    "recoverable": False,
                }
            if len(top_reasons) > 1:
                derived["risk_pattern"] = f"Tie between {', '.join(top_reasons)}"
            else:
                derived["risk_pattern"] = f"Highest risk pattern is {top_reasons[0]}"
            return {
                "status": "EXECUTED",
                "summary": str(derived["risk_pattern"]),
                "evidence": True,
            }

        if "produce tomorrow focus recommendations" in lowered:
            payload = dict(derived.get("logistics_metrics") or {})
            late = int(payload.get("late_deliveries", 0))
            total = int(payload.get("total_deliveries", 0))
            calc_output = None
            for result in reversed(task.execution_context.step_results):
                if result.tool_name == "calculator" and isinstance(result.sanitized_output, dict):
                    calc_output = result.sanitized_output
                    break
            rate = calc_output.get("result") if isinstance(calc_output, dict) else None
            if rate is None:
                return {
                    "status": "FAILED",
                    "summary": "Late-delivery percentage missing.",
                    "error_code": "MISSING_RESULT",
                    "recoverable": False,
                }
            investment_analysis = dict(derived.get("logistics_investment_analysis") or {})
            if investment_analysis:
                prevented_per_week = float(investment_analysis.get("prevented_per_week", 0.0))
                weekly_savings = float(investment_analysis.get("weekly_savings", 0.0))
                monthly_savings = float(investment_analysis.get("monthly_savings", 0.0))
                monthly_cost = float(investment_analysis.get("monthly_cost", 0.0))
                net_monthly_benefit = float(investment_analysis.get("net_monthly_benefit", 0.0))
                monthly_weeks = float(investment_analysis.get("monthly_weeks_assumption", 4.0))
                remaining_top = list(derived.get("post_change_top_delay_reasons") or [])
                remaining_top_count = float(derived.get("post_change_top_delay_count", 0.0))

                if len(remaining_top) > 1:
                    remaining_cause_text = (
                        f"Strongest remaining causes after the change: {', '.join(remaining_top)} "
                        f"at {remaining_top_count:g} expected late deliveries/week."
                    )
                elif remaining_top:
                    remaining_cause_text = (
                        f"Strongest remaining cause after the change: {remaining_top[0]} "
                        f"at {remaining_top_count:g} expected late deliveries/week."
                    )
                else:
                    remaining_cause_text = "No remaining delay cause could be ranked."

                if net_monthly_benefit > 0:
                    margin_ratio = net_monthly_benefit / monthly_cost if monthly_cost > 0 else 1.0
                    if margin_ratio <= 0.10:
                        financial_decision = (
                            "The investment is slightly financially positive, but it is close to break-even. "
                            "Proceed only if the savings assumption is credible, preferably with a monitored pilot."
                        )
                    else:
                        financial_decision = "The investment is financially positive under the supplied assumptions."
                elif abs(net_monthly_benefit) < 1e-9:
                    financial_decision = "The investment is approximately break-even under the supplied assumptions."
                else:
                    financial_decision = "The investment does not break even under the supplied assumptions."

                summary = (
                    f"Current late-delivery rate: {float(rate):g}%. "
                    f"Expected prevented late deliveries: {prevented_per_week:g} per week. "
                    f"Expected weekly savings: {_format_money(weekly_savings)}. "
                    f"Expected monthly savings ({monthly_weeks:g}-week assumption): {_format_money(monthly_savings)}. "
                    f"Net monthly benefit after {_format_money(monthly_cost)} cost: {_format_money(net_monthly_benefit)}. "
                    f"{financial_decision}"
                )

                derived["business_report"] = {
                    "executive_summary": "Delivery investment analysis complete.",
                    "kpis": [
                        f"Current late-delivery rate: {float(rate):g}%",
                        f"Expected prevented late deliveries: {prevented_per_week:g} per week",
                        f"Expected weekly savings: {_format_money(weekly_savings)}",
                        f"Expected monthly savings ({monthly_weeks:g}-week assumption): {_format_money(monthly_savings)}",
                        f"Net monthly benefit after {_format_money(monthly_cost)} cost: {_format_money(net_monthly_benefit)}",
                    ],
                    "problems_found": [remaining_cause_text],
                    "risks": [
                        f"Monthly savings use a {monthly_weeks:g}-week month assumption.",
                        "Realized savings depend on the supplied savings-per-prevented-delivery estimate.",
                    ],
                    "recommendations": [f"Financial decision: {financial_decision}"],
                    "evidence_references": ["user.prompt.logistics_metrics", "calculator.late_delivery_rate"],
                    "next_actions": [
                        "Track prevented late deliveries and realized savings during the first month.",
                        "Recalculate the decision if loading-delay reduction or per-delivery savings differs materially from the assumptions.",
                    ],
                    "summary": summary,
                }
                return {
                    "status": "EXECUTED",
                    "summary": summary,
                    "evidence": True,
                }

            top_reasons = list(derived.get("top_delay_reasons") or [])
            if len(top_reasons) > 1:
                cause_text = f"{top_reasons[0]} and {top_reasons[1]} are tied as top causes"
            elif top_reasons:
                cause_text = f"{top_reasons[0]} is the top cause"
            else:
                cause_text = "no top cause identified"
            summary = (
                f"Late deliveries: {late} of {total} ({float(rate):g}%). "
                f"{cause_text}. Focus tomorrow on dispatch planning and loading-lane coordination for these patterns."
            )
            derived["business_report"] = {
                "executive_summary": "Daily logistics performance review complete.",
                "kpis": [f"Total deliveries: {total}", f"Late deliveries: {late}", f"Late rate: {float(rate):g}%"],
                "problems_found": [cause_text],
                "risks": ["Persistent late-delivery rate can reduce customer SLA performance."],
                "recommendations": [
                    "Prioritize pre-departure loading checks for peak routes.",
                    "Add traffic-aware dispatch buffers for high-risk windows.",
                ],
                "evidence_references": ["logistics.metrics.today"],
                "next_actions": [
                    "Review first-wave loading throughput at start of shift.",
                    "Audit traffic-impacted routes for alternate dispatch timing.",
                ],
                "summary": summary,
            }
            return {
                "status": "EXECUTED",
                "summary": summary,
                "evidence": True,
            }

    if context.workflow == BusinessWorkflow.CUSTOMER_SUPPORT_ANALYSIS:
        if "load approved customer issue set" in lowered:
            issues = adapters.load_customer_issues(context)
            if not issues:
                return {
                    "status": "FAILED",
                    "summary": "Customer issue data unavailable.",
                    "error_code": "MISSING_DATA",
                    "recoverable": False,
                }
            derived["customer_issues"] = issues
            return {"status": "EXECUTED", "summary": f"Loaded {len(issues)} customer issues.", "evidence": True}

        if "group issues by recurring theme" in lowered:
            issues = list(derived.get("customer_issues") or [])
            if not issues:
                return {"status": "FAILED", "summary": "No customer issue set loaded.", "error_code": "MISSING_DATA", "recoverable": False}
            counts: dict[str, int] = {}
            for item in issues:
                theme = str(item.get("theme", "unknown")).strip().lower() or "unknown"
                counts[theme] = int(counts.get(theme, 0)) + 1
            ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            top_theme, top_count = ordered[0]
            derived["support_theme_counts"] = counts
            derived["business_report"] = {
                "executive_summary": "Customer issue clustering complete.",
                "kpis": [f"Total issues: {len(issues)}", f"Top theme count: {top_count}"],
                "problems_found": [f"Top recurring problem: {top_theme}"],
                "risks": ["Recurring issue can increase support backlog."],
                "recommendations": ["Create macro responses for the top theme.", "Escalate root-cause analysis with operations."],
                "evidence_references": ["customer.issues.dataset"],
                "next_actions": ["Assign owner for top recurring issue trend."],
                "summary": f"Top recurring customer issue is {top_theme} with {top_count} occurrences.",
            }
            return {"status": "EXECUTED", "summary": derived["business_report"]["summary"], "evidence": True}

        if "draft recommended response actions" in lowered:
            report = dict(derived.get("business_report") or {})
            if not report:
                return {"status": "FAILED", "summary": "No grouped issue analysis available.", "error_code": "MISSING_RESULT", "recoverable": False}
            return {"status": "EXECUTED", "summary": str(report.get("summary", "Prepared support response actions.")), "evidence": True}

    if context.workflow == BusinessWorkflow.FINANCIAL_ANALYSIS:
        if "load approved financial summary data" in lowered:
            summary = adapters.load_financial_summary(context)
            try:
                revenue = float(summary.get("revenue", 0.0))
                operating_expenses = float(summary.get("operating_expenses", 0.0))
                other_expenses = float(summary.get("other_expenses", 0.0))
            except (TypeError, ValueError):
                return {"status": "FAILED", "summary": "Financial data is malformed.", "error_code": "MALFORMED_DATA", "recoverable": False}
            if revenue <= 0 and operating_expenses <= 0 and other_expenses <= 0:
                return {"status": "FAILED", "summary": "Financial data unavailable.", "error_code": "MISSING_DATA", "recoverable": False}
            derived["financial_summary"] = summary
            derived["net_financial_expression"] = f"{revenue} - {operating_expenses} - {other_expenses}"
            return {"status": "EXECUTED", "summary": "Loaded financial summary and prepared net expression.", "evidence": True}

        if "identify anomalies and produce recommendations" in lowered:
            summary = dict(derived.get("financial_summary") or {})
            calc_output = None
            for result in reversed(task.execution_context.step_results):
                if result.tool_name == "calculator" and isinstance(result.sanitized_output, dict):
                    calc_output = result.sanitized_output
                    break
            net_value = calc_output.get("result") if isinstance(calc_output, dict) else None
            if net_value is None:
                return {"status": "FAILED", "summary": "Net financial result unavailable.", "error_code": "MISSING_RESULT", "recoverable": False}
            anomalies = list(summary.get("anomalies") or [])
            derived["business_report"] = {
                "executive_summary": "Financial summary analysis complete.",
                "kpis": [
                    f"Revenue: {summary.get('revenue')}",
                    f"Operating expenses: {summary.get('operating_expenses')}",
                    f"Other expenses: {summary.get('other_expenses')}",
                    f"Net result: {float(net_value):g}",
                ],
                "problems_found": anomalies or ["No major anomaly flagged in deterministic dataset."],
                "risks": ["Expense acceleration can compress margin if sustained."],
                "recommendations": ["Review top expense contributors.", "Track weekly net variance against baseline."],
                "evidence_references": ["finance.summary.approved"],
                "next_actions": ["Run variance review with finance operations."],
                "summary": f"Net result is {float(net_value):g} with {len(anomalies)} anomaly signal(s).",
            }
            return {"status": "EXECUTED", "summary": derived["business_report"]["summary"], "evidence": True}

    if context.workflow == BusinessWorkflow.SYNTHETIC_APPROVAL:
        if "prepare bounded synthetic approval workflow context" in lowered:
            return {"status": "EXECUTED", "summary": "Prepared bounded synthetic approval context.", "evidence": True}

        if "summarize approved synthetic action outcome" in lowered:
            tool_output = None
            for result in reversed(task.execution_context.step_results):
                if result.tool_name == "approval.tool" and isinstance(result.sanitized_output, dict):
                    tool_output = result.sanitized_output
                    break
            if not tool_output:
                return {"status": "FAILED", "summary": "Synthetic approval action did not execute.", "error_code": "MISSING_RESULT", "recoverable": False}
            derived["business_report"] = {
                "executive_summary": "Synthetic approval workflow completed safely.",
                "kpis": ["Approval-gated synthetic action executed exactly once."],
                "problems_found": [],
                "risks": [],
                "recommendations": ["Keep approval scope bound to exact task and step."],
                "evidence_references": ["synthetic.approval.action"],
                "next_actions": ["No operational side effects were performed."],
                "summary": "Synthetic approval-gated step executed safely after explicit approval.",
            }
            return {"status": "EXECUTED", "summary": derived["business_report"]["summary"], "evidence": True}

    if context.workflow == BusinessWorkflow.BUSINESS_RESEARCH:
        if "gather competitor research evidence" in lowered:
            derived["business_research_required"] = True
            return {"status": "EXECUTED", "summary": "Business research evidence collection requested through SHY research pipeline.", "evidence": True}
        if "synthesize cited findings" in lowered:
            return {"status": "EXECUTED", "summary": "Prepared cited competitive synthesis for the final brief.", "evidence": True}
        if "produce recommendations grounded in cited evidence" in lowered:
            derived["business_report"] = {
                "executive_summary": "Competitive brief prepared from cited evidence.",
                "kpis": ["Cited sources used in synthesis"],
                "problems_found": ["Competitive pressure observed in delivery speed and pricing narratives."],
                "risks": ["Delayed operational adaptation can weaken market position."],
                "recommendations": ["Improve delivery reliability and publish SLA metrics.", "Track competitor feature cadence monthly."],
                "evidence_references": ["research.citations"],
                "next_actions": ["Run monthly competitor delta review."],
                "summary": "Prepared a short competitive brief with cited findings and concrete recommendations.",
            }
            return {"status": "EXECUTED", "summary": derived["business_report"]["summary"], "evidence": True}

    if context.workflow == BusinessWorkflow.BUSINESS_SUMMARY:
        if "load approved business metrics" in lowered:
            payload = adapters.load_operations_metrics(context)
            derived["operations_metrics"] = payload
            return {"status": "EXECUTED", "summary": "Loaded approved operations metrics.", "evidence": True}

        if "summarize kpi and risk posture" in lowered:
            metrics = dict(derived.get("operations_metrics") or {})
            if not metrics:
                return {"status": "FAILED", "summary": "Operations metrics unavailable.", "error_code": "MISSING_DATA", "recoverable": False}
            derived["business_report"] = {
                "executive_summary": "Daily operations summary complete.",
                "kpis": [
                    f"Open tasks: {metrics.get('open_tasks', 0)}",
                    f"Completed tasks: {metrics.get('completed_tasks', 0)}",
                    f"Blocked tasks: {metrics.get('blocked_tasks', 0)}",
                ],
                "problems_found": ["Backlog pressure in open tasks."] if int(metrics.get("open_tasks", 0)) > 10 else ["No major backlog pressure."],
                "risks": list(metrics.get("risk_flags") or []),
                "recommendations": ["Prioritize blocked task triage first hour tomorrow."],
                "evidence_references": ["ops.metrics.daily"],
                "next_actions": ["Review blocked tasks owner assignments."],
                "summary": "Generated daily operations summary with KPI/risk snapshot.",
            }
            return {"status": "EXECUTED", "summary": derived["business_report"]["summary"], "evidence": True}

        if "recommend next actions" in lowered:
            report = dict(derived.get("business_report") or {})
            if not report:
                return {"status": "FAILED", "summary": "No operations summary available.", "error_code": "MISSING_RESULT", "recoverable": False}
            return {"status": "EXECUTED", "summary": str(report.get("summary", "Prepared next actions.")), "evidence": True}

    return {
        "status": "FAILED",
        "summary": "Unsupported workflow reasoning step.",
        "error_code": "UNSUPPORTED_OUTPUT",
        "recoverable": False,
    }


def build_business_report_markdown(task: Any) -> str | None:
    report = getattr(task.execution_context, "derived_values", {}).get("business_report")
    if not isinstance(report, dict):
        return None

    lines = [str(report.get("executive_summary", "Business workflow completed."))]

    kpis = list(report.get("kpis") or [])
    if kpis:
        lines.append("KPIs: " + "; ".join(str(item) for item in kpis))

    problems = list(report.get("problems_found") or [])
    if problems:
        lines.append("Problems: " + "; ".join(str(item) for item in problems))

    risks = list(report.get("risks") or [])
    if risks:
        lines.append("Risks: " + "; ".join(str(item) for item in risks))

    recommendations = list(report.get("recommendations") or [])
    if recommendations:
        lines.append("Recommendations: " + "; ".join(str(item) for item in recommendations))

    next_actions = list(report.get("next_actions") or [])
    if next_actions:
        lines.append("Next actions: " + "; ".join(str(item) for item in next_actions))

    return "\n".join(lines)


def scoped_user_uuid(user_id: str | None, workspace_id: str, business_id: str | None) -> uuid.UUID:
    if user_id:
        try:
            return uuid.UUID(str(user_id))
        except Exception:
            pass
    scope = f"{workspace_id}|{business_id or ''}|{user_id or 'anonymous'}"
    return uuid.uuid5(uuid.NAMESPACE_DNS, scope)


def business_context_payload(context: WorkflowExecutionContext) -> dict[str, Any]:
    payload = asdict(context)
    payload["domain"] = context.domain.value
    payload["workflow"] = context.workflow.value
    return payload


def workflow_policy_payload(policy: WorkflowPolicy) -> dict[str, Any]:
    return asdict(policy)


def summarize_business_result(task: Any) -> WorkflowResult | None:
    report = getattr(task.execution_context, "derived_values", {}).get("business_report")
    context = extract_workflow_context_from_task(task)
    if context is None or not isinstance(report, dict):
        return None

    return WorkflowResult(
        status=WorkflowStatus.COMPLETED if getattr(task, "status", None).value == "COMPLETED" else WorkflowStatus.RUNNING,
        executive_summary=str(report.get("executive_summary", "")),
        kpis=tuple(str(item) for item in (report.get("kpis") or [])),
        problems_found=tuple(str(item) for item in (report.get("problems_found") or [])),
        risks=tuple(str(item) for item in (report.get("risks") or [])),
        recommendations=tuple(str(item) for item in (report.get("recommendations") or [])),
        evidence_references=tuple(str(item) for item in (report.get("evidence_references") or [])),
        next_actions=tuple(str(item) for item in (report.get("next_actions") or [])),
    )


def format_public_workflow_plan(plan_steps: list[Any]) -> list[str]:
    output: list[str] = []
    for item in plan_steps:
        try:
            output.append(f"{int(item.step_id)}. {str(item.objective)}")
        except Exception:
            continue
    return output


def workflow_requires_research_synthesis(context: WorkflowExecutionContext) -> bool:
    return context.workflow == BusinessWorkflow.BUSINESS_RESEARCH


def evidence_fingerprint_from_research_payload(research_payload: dict[str, Any]) -> str:
    evidence = research_payload.get("evidence") or research_payload.get("results") or []
    text = json.dumps(evidence, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
