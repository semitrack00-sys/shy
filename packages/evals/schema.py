import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ScenarioCategory(str, Enum):
    CHAT_SANITY = "CHAT_SANITY"
    ROUTING = "ROUTING"
    DEEP_TASK = "DEEP_TASK"
    VERIFICATION = "VERIFICATION"
    RESEARCH = "RESEARCH"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    HALLUCINATION_RESISTANCE = "HALLUCINATION_RESISTANCE"
    TOOL_SELECTION = "TOOL_SELECTION"
    MEMORY = "MEMORY"
    CODING = "CODING"
    PERMISSIONS = "PERMISSIONS"
    FAILURE_RECOVERY = "FAILURE_RECOVERY"
    PROMPT_INJECTION = "PROMPT_INJECTION"


_ALLOWED_CAPABILITIES = {
    "CHAT",
    "REASONING",
    "RESEARCH",
    "CODING",
    "MEMORY",
    "TOOL",
    "MULTI_STEP",
}

_ALLOWED_VERIFICATION = {"PASS", "CORRECTABLE", "FAIL"}

_ALLOWED_STATUS = {
    "COMPLETE",
    "PARTIAL",
    "FAILED",
    "FINISHED",
    "AWAITING_APPROVAL",
    "RESPOND",
    "TOOL_RESULT",
    "DENIED",
}

_ALLOWED_ISSUE_TYPES = {
    "UNSUPPORTED_CLAIM",
    "MISSING_EVIDENCE",
    "CITATION_INVALID",
    "CITATION_MISMATCH",
    "CONTRADICTORY_EVIDENCE",
    "TOOL_RESULT_MISMATCH",
    "INCOMPLETE_RESULT",
    "INSUFFICIENT_EVIDENCE",
    "VERIFICATION_UNAVAILABLE",
    "UNSUPPORTED_OUTPUT",
}


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    category: ScenarioCategory
    description: str
    input_data: dict[str, Any]
    expected: dict[str, Any]
    constraints: dict[str, Any]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class EvalSuite:
    schema_version: str
    suite_name: str
    suite_version: str
    baseline_commit: str
    scenarios: tuple[Scenario, ...]


def load_suite(path: str | Path) -> EvalSuite:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("suite root must be an object")

    schema_version = str(data.get("schema_version", "")).strip()
    suite_name = str(data.get("suite_name", "")).strip()
    suite_version = str(data.get("suite_version", "")).strip()
    baseline_commit = str(data.get("baseline_commit", "")).strip()

    if not schema_version:
        raise ValueError("schema_version is required")
    if not suite_name:
        raise ValueError("suite_name is required")
    if not suite_version:
        raise ValueError("suite_version is required")

    raw_scenarios = data.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ValueError("scenarios must be a non-empty list")

    scenarios: list[Scenario] = []
    seen_ids: set[str] = set()

    for raw in raw_scenarios:
        scenario = _parse_scenario(raw)
        if scenario.scenario_id in seen_ids:
            raise ValueError(f"duplicate scenario id: {scenario.scenario_id}")
        seen_ids.add(scenario.scenario_id)
        scenarios.append(scenario)

    return EvalSuite(
        schema_version=schema_version,
        suite_name=suite_name,
        suite_version=suite_version,
        baseline_commit=baseline_commit,
        scenarios=tuple(scenarios),
    )


def _parse_scenario(raw: Any) -> Scenario:
    if not isinstance(raw, dict):
        raise ValueError("scenario entry must be an object")

    scenario_id = str(raw.get("id", "")).strip()
    if not scenario_id:
        raise ValueError("scenario id is required")

    category_text = str(raw.get("category", "")).strip()
    try:
        category = ScenarioCategory(category_text)
    except Exception as exc:
        raise ValueError(f"unknown category: {category_text}") from exc

    description = str(raw.get("description", "")).strip()
    if not description:
        raise ValueError(f"description is required for scenario: {scenario_id}")

    input_data = raw.get("input", {})
    expected = raw.get("expected", {})
    constraints = raw.get("constraints", {})
    tags = raw.get("tags", [])

    if not isinstance(input_data, dict):
        raise ValueError(f"input must be object for scenario: {scenario_id}")
    if not isinstance(expected, dict):
        raise ValueError(f"expected must be object for scenario: {scenario_id}")
    if not isinstance(constraints, dict):
        raise ValueError(f"constraints must be object for scenario: {scenario_id}")
    if not isinstance(tags, list):
        raise ValueError(f"tags must be list for scenario: {scenario_id}")

    _validate_expected(scenario_id, expected)
    _validate_constraints(scenario_id, constraints)

    return Scenario(
        scenario_id=scenario_id,
        category=category,
        description=description,
        input_data=input_data,
        expected=expected,
        constraints=constraints,
        tags=tuple(str(tag).strip() for tag in tags if str(tag).strip()),
    )


def _validate_expected(scenario_id: str, expected: dict[str, Any]):
    capability = expected.get("expected_capability")
    if capability is not None and str(capability) not in _ALLOWED_CAPABILITIES:
        raise ValueError(f"invalid expected_capability in scenario: {scenario_id}")

    status = expected.get("expected_status")
    if status is not None and str(status) not in _ALLOWED_STATUS:
        raise ValueError(f"invalid expected_status in scenario: {scenario_id}")

    verification = expected.get("expected_verification")
    if verification is not None and str(verification) not in _ALLOWED_VERIFICATION:
        raise ValueError(f"invalid expected_verification in scenario: {scenario_id}")

    for field_name in ("required_issue_types", "forbidden_issue_types"):
        value = expected.get(field_name)
        if value is None:
            continue
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be list in scenario: {scenario_id}")
        for item in value:
            if str(item) not in _ALLOWED_ISSUE_TYPES:
                raise ValueError(f"invalid issue type {item} in scenario: {scenario_id}")

    for field_name in ("required_tool", "expected_conflict", "expected_citation_validity", "requires_evidence"):
        value = expected.get(field_name)
        if field_name == "required_tool" and value is not None and not str(value).strip():
            raise ValueError(f"required_tool cannot be empty in scenario: {scenario_id}")
        if field_name != "required_tool" and value is not None and not isinstance(value, bool):
            raise ValueError(f"{field_name} must be boolean in scenario: {scenario_id}")

    for field_name in (
        "expected_provider",
        "expected_model",
        "expected_selection_reason",
        "expected_failure_category",
        "expected_required_capability",
    ):
        value = expected.get(field_name)
        if value is not None and not str(value).strip():
            raise ValueError(f"{field_name} cannot be empty in scenario: {scenario_id}")

    for field_name in ("max_attempts", "max_escalations"):
        value = expected.get(field_name)
        if value is None:
            continue
        if not isinstance(value, int) or value < 0 or value > 10:
            raise ValueError(f"{field_name} must be integer between 0 and 10 in scenario: {scenario_id}")

    forbidden_tools = expected.get("forbidden_tools")
    if forbidden_tools is not None:
        if not isinstance(forbidden_tools, list):
            raise ValueError(f"forbidden_tools must be list in scenario: {scenario_id}")
        for tool in forbidden_tools:
            if not str(tool).strip():
                raise ValueError(f"forbidden_tools contains empty value in scenario: {scenario_id}")


def _validate_constraints(scenario_id: str, constraints: dict[str, Any]):
    numeric_fields = {
        "max_tool_calls": (0, 20),
        "max_iterations": (0, 10),
        "max_queries": (0, 8),
        "follow_up_budget": (0, 4),
    }

    for key, (minimum, maximum) in numeric_fields.items():
        value = constraints.get(key)
        if value is None:
            continue
        if not isinstance(value, int):
            raise ValueError(f"{key} must be integer in scenario: {scenario_id}")
        if value < minimum or value > maximum:
            raise ValueError(f"{key} outside allowed range in scenario: {scenario_id}")

    for key in ("critical",):
        value = constraints.get(key)
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"{key} must be boolean in scenario: {scenario_id}")
