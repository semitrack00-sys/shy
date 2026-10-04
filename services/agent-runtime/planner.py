import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import importlib.util


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_business_module = _load_module(
    "shy_business_workflows",
    Path(__file__).resolve().parent / "business_workflows.py",
)

resolve_business_intent = _business_module.resolve_business_intent
WorkflowInput = _business_module.WorkflowInput
build_workflow_execution_context = _business_module.build_workflow_execution_context
build_workflow_plan = _business_module.build_workflow_plan
business_context_payload = _business_module.business_context_payload
workflow_policy_payload = _business_module.workflow_policy_payload


DEFAULT_MAX_STEPS = 5
HARD_MAX_STEPS = 8
ENABLE_SYNTHETIC_TASK_TOOLS = os.getenv("SHY_ENABLE_SYNTHETIC_TASK_TOOLS", "0").strip() == "1"


class StepType(str, Enum):
    RESPOND = "RESPOND"
    TOOL = "TOOL"


class ExecutionMode(str, Enum):
    DIRECT = "DIRECT"
    SINGLE_TOOL = "SINGLE_TOOL"
    MULTI_STEP = "MULTI_STEP"


@dataclass(frozen=True)
class AgentStep:
    step_type: StepType
    reason: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlannerDecision:
    mode: ExecutionMode
    reason: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None


class AgentPlanner:
    """
    SHY Agent Planner v0.7.

    The planner may propose an action.
    It cannot execute tools and cannot grant approval.
    """

    def decide(self, message: str) -> PlannerDecision:
        text = message.lower().strip()

        business_intent = resolve_business_intent(message)
        if business_intent is not None:
            return PlannerDecision(
                mode=ExecutionMode.MULTI_STEP,
                reason=business_intent.reason,
            )

        if ENABLE_SYNTHETIC_TASK_TOOLS and "approval workflow validation" in text:
            return PlannerDecision(
                mode=ExecutionMode.MULTI_STEP,
                reason="Synthetic approval workflow validation requires a bounded multi-step task.",
            )

        if ENABLE_SYNTHETIC_TASK_TOOLS and "step limit validation" in text:
            return PlannerDecision(
                mode=ExecutionMode.MULTI_STEP,
                reason="Synthetic step-limit validation requires a bounded multi-step task.",
            )

        if self._is_health_percentage_request(text):
            return PlannerDecision(
                mode=ExecutionMode.MULTI_STEP,
                reason="The request requires ordered health inspection, calculation, and verification.",
            )

        if self._is_calculator_request(message):
            expression = message.strip()
            percent_match = re.search(r"([0-9]*\.?[0-9]+\s*%\s*of\s*[0-9]*\.?[0-9]+)", message, re.IGNORECASE)
            if percent_match:
                expression = percent_match.group(1)
            return PlannerDecision(
                mode=ExecutionMode.SINGLE_TOOL,
                reason="The request requires deterministic arithmetic.",
                tool_name="calculator",
                arguments={"expression": expression},
            )

        health_phrases = (
            "system health",
            "shy health",
            "health status",
            "are you healthy",
            "check your health",
            "database connected",
            "database status",
        )

        if any(phrase in text for phrase in health_phrases):
            return PlannerDecision(
                mode=ExecutionMode.SINGLE_TOOL,
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
                    return PlannerDecision(
                        mode=ExecutionMode.SINGLE_TOOL,
                        reason="The request requires current public web research.",
                        tool_name="web.search",
                        arguments={
                            "query": query,
                            "max_results": 5,
                        },
                    )

        return PlannerDecision(
            mode=ExecutionMode.DIRECT,
            reason="No tool is required for this request.",
        )

    def plan(self, message: str) -> AgentStep:
        decision = self.decide(message)

        if decision.mode == ExecutionMode.SINGLE_TOOL:
            return AgentStep(
                step_type=StepType.TOOL,
                reason=decision.reason,
                tool_name=decision.tool_name,
                arguments=decision.arguments,
            )

        return AgentStep(
            step_type=StepType.RESPOND,
            reason=decision.reason,
        )

    def build_task_plan(
        self,
        message: str,
        max_steps: int = DEFAULT_MAX_STEPS,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        context = context or {}
        planning_message = str(context.get("original_message") or message)
        decision = self.decide(planning_message)
        effective_max_steps = max(1, min(int(max_steps), HARD_MAX_STEPS))

        if decision.mode != ExecutionMode.MULTI_STEP:
            return None

        business_intent = resolve_business_intent(planning_message)
        if business_intent is not None:
            workflow_context = build_workflow_execution_context(
                WorkflowInput(
                    objective=planning_message.strip(),
                    conversation_id=context.get("conversation_id"),
                    user_id=context.get("user_id"),
                    workspace_id=str(context.get("workspace_id") or "default"),
                    business_id=context.get("business_id"),
                ),
                business_intent,
            )
            plan = build_workflow_plan(workflow_context, planning_message.strip())
            plan["maximum_step_count"] = min(
                int(plan.get("maximum_step_count", effective_max_steps)),
                effective_max_steps,
            )
            plan["workflow_context"] = business_context_payload(workflow_context)
            plan["workflow_policy"] = workflow_policy_payload(workflow_context.policy)
            return plan

        lowered = message.lower().strip()

        if ENABLE_SYNTHETIC_TASK_TOOLS and "approval workflow validation" in lowered:
            return {
                "goal": message.strip(),
                "maximum_step_count": effective_max_steps,
                "completion_criteria": "Approval-gated step executes exactly once and the remaining bounded steps complete.",
                "failure_policy": "Stop immediately when approval is required or approval mismatches.",
                "steps": [
                    {
                        "step_id": 1,
                        "action_type": "TOOL",
                        "objective": "Run the synthetic approval-gated tool.",
                        "tool_name": "approval.tool",
                        "tool_args": {"recipient": "approval-test", "message": "validate"},
                    },
                    {
                        "step_id": 2,
                        "action_type": "REASON",
                        "objective": "Confirm the approval step result and prepare the public summary.",
                    },
                ],
            }

        if ENABLE_SYNTHETIC_TASK_TOOLS and "step limit validation" in lowered:
            return {
                "goal": message.strip(),
                "maximum_step_count": HARD_MAX_STEPS + 4,
                "completion_criteria": "Never execute more than the hard maximum number of steps.",
                "failure_policy": "Fail safely when the plan exceeds the hard maximum.",
                "steps": [
                    {
                        "step_id": index,
                        "action_type": "REASON",
                        "objective": f"Synthetic bounded step {index}",
                    }
                    for index in range(1, HARD_MAX_STEPS + 2)
                ],
            }

        return {
            "goal": message.strip(),
            "maximum_step_count": effective_max_steps,
            "completion_criteria": "Health snapshot inspected, connected-service percentage calculated, and final answer verified.",
            "failure_policy": "Stop on approval requirement, forbidden action, malformed output, duplicate step, or repeated failure.",
            "steps": [
                {
                    "step_id": 1,
                    "action_type": "TOOL",
                    "objective": "Check SHY runtime health.",
                    "tool_name": "system.health",
                    "tool_args": {},
                },
                {
                    "step_id": 2,
                    "action_type": "REASON",
                    "objective": "Inspect the health snapshot and prepare a calculator expression for connected required services.",
                },
                {
                    "step_id": 3,
                    "action_type": "TOOL",
                    "objective": "Calculate the percentage of required services that are connected.",
                    "tool_name": "calculator",
                    "tool_args": {
                        "expression_context_key": "service_connection_expression",
                    },
                },
                {
                    "step_id": 4,
                    "action_type": "REASON",
                    "objective": "Compose the final answer from the verified task results.",
                },
            ],
        }

    @staticmethod
    def _is_health_percentage_request(text: str) -> bool:
        health_terms = (
            "health",
            "database connected",
            "services are connected",
            "required services",
        )
        calculation_terms = (
            "percentage",
            "percent",
            "calculate",
        )

        return any(term in text for term in health_terms) and any(
            term in text for term in calculation_terms
        )

    @staticmethod
    def _is_calculator_request(message: str) -> bool:
        text = message.lower().strip()
        return bool(re.search(r"\d", text)) and any(
            marker in text for marker in ("what is", "calculate", "compute", "%")
        )
