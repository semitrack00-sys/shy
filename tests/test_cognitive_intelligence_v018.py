import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"

sys.path.insert(0, str(SERVICES))
sys.path.insert(0, str(SERVICES / "core"))


for package_name, package_path in (
    ("tools", SERVICES / "tools"),
    ("permissions", SERVICES / "permissions"),
):
    package = __import__("types").ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package

for module_name, module_path in (
    ("tools.contracts", SERVICES / "tools" / "contracts.py"),
    ("tools.gateway", SERVICES / "tools" / "gateway.py"),
    ("permissions.policy", SERVICES / "permissions" / "policy.py"),
    ("permissions.approvals", SERVICES / "permissions" / "approvals.py"),
):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


cognitive_spec = importlib.util.spec_from_file_location(
    "shy_cognitive_engine_v018",
    SERVICES / "agent-runtime" / "cognitive_engine.py",
)
cognitive = importlib.util.module_from_spec(cognitive_spec)
sys.modules["shy_cognitive_engine_v018"] = cognitive
cognitive_spec.loader.exec_module(cognitive)


ToolGateway = sys.modules["tools.gateway"].ToolGateway
ToolDefinition = sys.modules["tools.contracts"].ToolDefinition
ToolRequest = sys.modules["tools.contracts"].ToolRequest
PermissionLevel = sys.modules["tools.contracts"].PermissionLevel
ToolRegistry = sys.modules["tools.contracts"].ToolRegistry


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


# Mathematics + independent verification.
revenue = 180000
expenses = 117000
net_profit = revenue - expenses
investment = int(net_profit * 0.40)
_assert(net_profit == 63000, "net profit must be 63,000")
_assert(investment == 25200, "investment must be 25,200")

verification = cognitive.verify_calculation(
    expected={"net_profit": 63000, "investment": 25200},
    observed={"net_profit": net_profit, "investment": investment},
)
_assert(
    verification.status == cognitive.VerificationStatus.VERIFIED,
    "independent calculation verification must pass",
)
print("mathematics + independent verification: PASS")


# Diagnosis with deterministic evidence.
late_rate = round((18 / 100) * 100, 2)
_assert(late_rate == 18.0, "late percentage must be 18%")

hypotheses = cognitive.build_hypotheses_from_delivery_evidence(
    total_deliveries=100,
    late_deliveries=18,
    traffic_delays=5,
    loading_delays=9,
    mechanical_delays=4,
)

strongest = max(hypotheses, key=lambda item: item.confidence)
_assert(strongest.name == "loading_delays", "loading delay must be strongest supported cause")
_assert(
    all(item.name != "dispatch_scheduling" for item in hypotheses),
    "unsupported alternatives must not be presented as fact",
)
print("diagnosis evidence weighting: PASS")


# Contradiction detection.
contradictions = cognitive.detect_contradictions(
    {
        "late_deliveries": ["18", "24"],
        "total_deliveries": ["100", "100"],
    }
)
_assert(len(contradictions) == 1, "one contradiction must be detected")
_assert(contradictions[0].field == "late_deliveries", "conflicting late delivery metric must be flagged")
print("contradiction detection: PASS")


# Insufficient evidence.
insufficient = cognitive.verify_calculation(expected={}, observed={"result": 1})
_assert(
    insufficient.status == cognitive.VerificationStatus.INSUFFICIENT_EVIDENCE,
    "insufficient evidence must be surfaced explicitly",
)
print("insufficient evidence handling: PASS")


# Candidate comparison.
candidates = [
    cognitive.CandidateApproach(
        name="strategy_a",
        correctness=0.8,
        feasibility=0.7,
        evidence=0.7,
        cost=0.3,
        risk=0.35,
        constraints_fit=0.75,
        expected_outcome=0.72,
    ),
    cognitive.CandidateApproach(
        name="strategy_b",
        correctness=0.9,
        feasibility=0.82,
        evidence=0.85,
        cost=0.4,
        risk=0.25,
        constraints_fit=0.88,
        expected_outcome=0.86,
    ),
    cognitive.CandidateApproach(
        name="strategy_c",
        correctness=0.74,
        feasibility=0.9,
        evidence=0.6,
        cost=0.15,
        risk=0.45,
        constraints_fit=0.7,
        expected_outcome=0.68,
    ),
]
ranking = cognitive.evaluate_candidates(candidates)
_assert(ranking.selected is not None, "candidate selection must produce a winner")
_assert(ranking.selected.name == "strategy_b", "deterministic criteria should select strategy_b")
print("candidate comparison: PASS")


# Critic catches incorrect candidate output.
critic = cognitive.run_critic(
    candidate_answer={"net_profit": 60000, "investment": 28000, "fabricated_evidence": False},
    expected_constraints={"expected_net_profit": 63000, "expected_investment": 25200},
)
_assert(any(issue.issue_type == "arithmetic_mistake" for issue in critic.issues), "critic must detect arithmetic errors")
print("critic checks: PASS")


# Verifier distinguishes correct and incorrect answers.
ok = cognitive.verify_calculation(
    expected={"value": 10},
    observed={"value": 10},
)
bad = cognitive.verify_calculation(
    expected={"value": 10},
    observed={"value": 9},
)
_assert(ok.status == cognitive.VerificationStatus.VERIFIED, "correct answer must verify")
_assert(bad.status == cognitive.VerificationStatus.FAILED_VERIFICATION, "incorrect answer must fail verification")
print("verifier distinction: PASS")


# Memory relevance + isolation.
memory_rows = [
    {
        "workspace_id": "workspace-a",
        "business_id": "business-a",
        "category": "PROJECT",
        "content": "Project Atlas uses PostgreSQL.",
        "status": "ACTIVE",
    },
    {
        "workspace_id": "workspace-b",
        "business_id": "business-b",
        "category": "USER_FACT",
        "content": "Company is Fabrikam.",
        "status": "ACTIVE",
    },
    {
        "workspace_id": "workspace-a",
        "business_id": "business-a",
        "category": "TASK_OUTCOME",
        "content": "Temporary scratchpad",
        "status": "SUPERSEDED",
    },
]

selected_a = cognitive.filter_relevant_memory(memory_rows, "workspace-a", "business-a")
selected_b = cognitive.filter_relevant_memory(memory_rows, "workspace-b", "business-b")

_assert(len(selected_a) == 1, "workspace A should only receive active A records")
_assert("PostgreSQL" in selected_a[0]["content"], "relevant memory must be preserved")
_assert(len(selected_b) == 1, "workspace B should only receive B records")
_assert("Fabrikam" in selected_b[0]["content"], "B memory should remain isolated")
print("memory relevance + isolation: PASS")


# Tool safety: cognitive decision can request tool use, but gateway policy still enforces permission.
registry = ToolRegistry()
registry.register(
    ToolDefinition(
        tool_id="safe.read",
        name="safe.read",
        description="Safe read-only tool",
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        permission_level=PermissionLevel.READ_ONLY,
        timeout_seconds=2.0,
    ),
    lambda: {"ok": True},
)
registry.register(
    ToolDefinition(
        tool_id="unsafe.mutate",
        name="unsafe.mutate",
        description="Forbidden mutation tool",
        input_schema={"type": "object", "properties": {}, "required": []},
        output_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        permission_level=PermissionLevel.FORBIDDEN,
        timeout_seconds=2.0,
    ),
    lambda: {"ok": True},
)

safe_gateway = ToolGateway(registry=registry)

denied = safe_gateway.execute_request(
    ToolRequest(
        tool_id="unsafe.mutate",
        arguments={},
        conversation_id="v018-cognitive",
        request_id="v018-cognitive-unsafe",
    )
)
_assert(denied.status == "DENIED", "cognitive layer must not bypass gateway permission policy")
print("tool safety policy enforcement: PASS")


# Core cognitive contracts and safe metadata.
complexity = cognitive.classify_complexity("Evaluate several architectures and recommend the best design under competing constraints.")
_assert(complexity == cognitive.CognitiveComplexity.DEEP, "deep complexity classification must trigger for architecture tradeoffs")

understanding = cognitive.understand_problem("Diagnose why delivery performance dropped using several metrics.")
plan = cognitive.decompose_problem(understanding)
_assert(plan.bounded is True, "decomposition plan must remain bounded")
_assert(len(plan.steps) <= 6, "decomposition must enforce hard limits")

metadata = cognitive.build_cognitive_metadata(
    complexity=complexity,
    decomposition=plan,
    hypotheses=hypotheses,
    verification_status=cognitive.VerificationStatus.PARTIALLY_VERIFIED,
    confidence=0.74,
    uncertainty_flags=cognitive.classify_uncertainty({"late_rate": cognitive.UncertaintyType.DERIVED}),
    evidence_sources_count=2,
    tools_used=("safe.read",),
    model_role=cognitive.recommended_model_role(complexity),
    selected_provider="ollama",
    executed_provider="ollama",
)

_assert(metadata.decomposition_count == len(plan.steps), "safe metadata should include decomposition count")
_assert(metadata.hypotheses_considered == len(hypotheses), "safe metadata should include hypotheses count")
_assert(metadata.executed_provider == "ollama", "executed provider metadata must be preserved")
print("core cognitive contracts + metadata: PASS")


print("SHY v0.18 cognitive intelligence checkpoint tests: PASS")
