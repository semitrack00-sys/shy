import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERT_PATH = ROOT / "services" / "agent-runtime" / "expert_intelligence.py"

spec = importlib.util.spec_from_file_location("shy_expert_intelligence_v020", EXPERT_PATH)
expert = importlib.util.module_from_spec(spec)
sys.modules["shy_expert_intelligence_v020"] = expert
spec.loader.exec_module(expert)


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


# Logistics economics should remain operationally grounded rather than being
# reclassified as generic finance just because cost/savings are present.
logistics = expert.select_expert(
    """I run a delivery company with late deliveries caused by loading delays.
    A loading system costs $2,000 per month and each prevented late delivery saves $120.
    Analyze whether I should buy it."""
)
_assert(logistics.domain == expert.ExpertDomain.LOGISTICS, "delivery investment analysis should select logistics expertise")
_assert(logistics.risk_level == expert.ExpertRiskLevel.MEDIUM, "recommendation should carry medium decision risk")
_assert(logistics.requires_verification is True, "logistics recommendation should require verification")
_assert(logistics.requires_research is False, "self-contained supplied metrics should not force web research")
_assert(logistics.answer_boundary == expert.ExpertAnswerBoundary.VERIFY, "self-contained logistics economics should be answerable with verification")
print("logistics expert selection: PASS")


software = expert.select_expert(
    "Diagnose this Python API traceback and recommend the safest code fix with unit tests."
)
_assert(software.domain == expert.ExpertDomain.SOFTWARE_ENGINEERING, "software traceback should select software expertise")
_assert(software.profile.default_model_role == "CODING", "software expert should prefer CODING role")
_assert(software.requires_verification is True, "software diagnosis should require verification")
print("software expert selection: PASS")


finance = expert.select_expert(
    "Calculate ROI, break-even, profit margin, and cash flow for this investment using the numbers I supplied."
)
_assert(finance.domain == expert.ExpertDomain.FINANCIAL_ANALYSIS, "financial metrics should select financial analysis")
_assert(finance.requires_research is False, "supplied finance inputs should not force current external data")
_assert(finance.evidence_requirement == expert.EvidenceRequirement.USER_SUPPLIED, "self-contained finance should use supplied evidence")
print("financial expert selection: PASS")


current_market = expert.select_expert(
    "What is the current market price and latest news for this investment?"
)
_assert(current_market.requires_research is True, "current market question should require research")
_assert(current_market.evidence_requirement == expert.EvidenceRequirement.EXTERNAL_CURRENT, "current market question should require external-current evidence")
_assert(current_market.answer_boundary == expert.ExpertAnswerBoundary.RESEARCH_REQUIRED, "missing current sources should block a definitive answer")
_assert(current_market.confidence_ceiling <= 0.62, "missing current evidence must cap confidence")
print("current-data escalation: PASS")


policy_mode, policy_decision = expert.apply_expert_response_policy(
    "What is the current market price and latest news for this investment?",
    "direct",
)
_assert(policy_mode == "research", "expert policy must escalate current data from direct to research")
_assert(policy_decision.requires_research is True, "expert policy escalation must retain the expert decision")

verify_mode, verify_decision = expert.apply_expert_response_policy(
    "Compare PostgreSQL and MySQL for a software architecture and recommend the safer tradeoffs.",
    "direct",
)
_assert(verify_mode == "verify", "expert policy must escalate expert recommendations from direct to verify")
_assert(verify_decision.domain == expert.ExpertDomain.SOFTWARE_ENGINEERING, "verify escalation should preserve domain")

preserved_research_mode, _ = expert.apply_expert_response_policy(
    "Explain a general concept.",
    "research",
)
_assert(preserved_research_mode == "research", "expert policy must never downgrade an existing research mode")
print("expert response-policy escalation: PASS")


regulated = expert.select_expert(
    "Give me legal advice on whether this contract is enforceable."
)
_assert(regulated.risk_level == expert.ExpertRiskLevel.REGULATED, "legal advice should be regulated-risk")
_assert(regulated.requires_authoritative_sources is True, "regulated request should require authoritative sources")
_assert(regulated.requires_research is True, "regulated request should require evidence lookup")
_assert(regulated.evidence_requirement == expert.EvidenceRequirement.AUTHORITATIVE, "regulated request should require authoritative evidence")
_assert(regulated.answer_boundary == expert.ExpertAnswerBoundary.AUTHORITATIVE_EVIDENCE_REQUIRED, "no authoritative evidence should block a definitive expert answer")
_assert(regulated.confidence_ceiling <= 0.58, "regulated request must cap confidence")
print("regulated-risk escalation: PASS")


high_stakes_finance = expert.select_expert(
    "Should I buy this stock today for my retirement portfolio?"
)
_assert(high_stakes_finance.risk_level == expert.ExpertRiskLevel.HIGH, "personal retirement stock recommendation should be high risk")
_assert(high_stakes_finance.requires_research is True, "high-stakes finance should require research")
_assert(high_stakes_finance.requires_authoritative_sources is True, "high-stakes finance must require authoritative sources")
_assert(high_stakes_finance.evidence_requirement == expert.EvidenceRequirement.AUTHORITATIVE, "high-stakes finance should require authoritative evidence")
_assert(high_stakes_finance.answer_boundary == expert.ExpertAnswerBoundary.AUTHORITATIVE_EVIDENCE_REQUIRED, "high-stakes finance without an authoritative source must remain blocked")
_assert(high_stakes_finance.confidence_ceiling <= 0.68, "high-stakes finance must have a bounded confidence ceiling")
print("high-stakes finance escalation: PASS")


conflicted = expert.select_expert(
    "Recommend whether Project Atlas should keep PostgreSQL.",
    knowledge_boundary="CONFLICTING_KNOWLEDGE",
    evidence_sources_count=3,
)
_assert(conflicted.answer_boundary == expert.ExpertAnswerBoundary.CLARIFICATION_REQUIRED, "conflicting knowledge should require clarification")
_assert(conflicted.confidence_ceiling <= 0.45, "conflicting knowledge must sharply cap confidence")
print("knowledge conflict boundary: PASS")


missing = expert.select_expert(
    "Recommend the best architecture.",
    knowledge_boundary="DATA_REQUIRED",
)
_assert(missing.answer_boundary == expert.ExpertAnswerBoundary.DATA_REQUIRED, "missing required knowledge should remain data-required")
_assert(missing.confidence_ceiling <= 0.55, "missing evidence must cap confidence")
print("missing knowledge boundary: PASS")


research = expert.select_expert(
    "Research the latest AI infrastructure releases and compare sources with citations.",
    evidence_sources_count=4,
)
_assert(research.domain == expert.ExpertDomain.RESEARCH, "explicit source comparison should select research expertise")
_assert(research.requires_research is True, "research domain must require research")
_assert(research.answer_boundary == expert.ExpertAnswerBoundary.VERIFY, "available evidence should permit verified synthesis")
print("research expert selection: PASS")


data = expert.select_expert(
    "Analyze these numbers for variance, correlation, trend, and forecast."
)
_assert(data.domain == expert.ExpertDomain.DATA_ANALYSIS, "statistical analysis should select data expertise")
_assert(data.requires_verification is True, "data analysis should require verification")
print("data expert selection: PASS")


general = expert.select_expert("Explain why the sky looks blue.")
_assert(general.domain == expert.ExpertDomain.GENERAL, "generic explanation should stay general")
_assert(general.answer_boundary == expert.ExpertAnswerBoundary.ANSWER, "low-risk general question should be directly answerable")
print("general expert fallback: PASS")


metadata = expert.public_expert_metadata(logistics)
_assert(metadata["domain"] == "LOGISTICS", "public metadata must expose selected domain")
_assert(metadata["expert_role"] == "REASONING", "public metadata must expose safe role recommendation")
_assert("matched_signals" not in metadata, "public metadata must not expose internal classifier markers")
_assert("reasoning" not in " ".join(str(key).lower() for key in metadata.keys() if key not in {"expert_role"}), "public metadata must not expose hidden reasoning fields")
print("public expert metadata privacy: PASS")


authority_count = expert.count_authoritative_research_sources(
    [
        {"domain": "www.sec.gov"},
        {"domain": "investor.example.com"},
        {"domain": "www.irs.gov"},
        {"domain": "sec.gov"},
        {"domain": "who.int"},
    ]
)
_assert(authority_count == 3, f"authoritative source count should dedupe official domains, got {authority_count}")
_assert(expert.is_authoritative_research_domain("www.sec.gov") is True, "SEC must be recognized as authoritative")
_assert(expert.is_authoritative_research_domain("blog.example.com") is False, "ordinary web sources must not be treated as authoritative")
print("authoritative research source recognition: PASS")


non_authoritative_high_stakes = expert.select_expert(
    "Should I buy this stock today for my retirement portfolio?",
    evidence_sources_count=4,
    authoritative_sources_count=0,
)
_assert(
    non_authoritative_high_stakes.answer_boundary == expert.ExpertAnswerBoundary.AUTHORITATIVE_EVIDENCE_REQUIRED,
    "multiple non-authoritative sources must not satisfy high-stakes evidence policy",
)
non_authoritative_frame = expert.build_expert_response_frame(
    non_authoritative_high_stakes,
    evidence_sources_count=4,
    authoritative_sources_count=0,
    verification_status="PARTIALLY_VERIFIED",
)
_assert(non_authoritative_frame.confidence_band == expert.ExpertConfidenceBand.LOW, "insufficient high-stakes authority must remain LOW confidence")
_assert(non_authoritative_frame.authoritative_sources_sufficient is False, "authority sufficiency must be false")
_assert(non_authoritative_frame.next_evidence_needed == ("authoritative_source",), "next evidence must explicitly request an authoritative source")
print("non-authoritative high-stakes evidence rejected: PASS")


authoritative_high_stakes = expert.select_expert(
    "Should I buy this stock today for my retirement portfolio?",
    evidence_sources_count=4,
    authoritative_sources_count=1,
)
_assert(
    authoritative_high_stakes.answer_boundary == expert.ExpertAnswerBoundary.VERIFY,
    "authoritative evidence should permit a verification-bounded high-stakes answer",
)
authoritative_frame = expert.build_expert_response_frame(
    authoritative_high_stakes,
    evidence_sources_count=4,
    authoritative_sources_count=1,
    grounding_status="GROUNDED",
    verification_status="VERIFIED",
)
_assert(authoritative_frame.authoritative_sources_sufficient is True, "authoritative evidence sufficiency must be true")
_assert(authoritative_frame.next_evidence_needed == (), "verified authoritative evidence should not request another mandatory source")
print("authoritative high-stakes evidence accepted for verification: PASS")


grounded_decision = expert.select_expert(
    "Evaluate the software architecture and recommend the safest design.",
    knowledge_boundary="ANSWERABLE",
    evidence_sources_count=2,
    authoritative_sources_count=1,
)
grounded_frame = expert.build_expert_response_frame(
    grounded_decision,
    evidence_sources_count=2,
    authoritative_sources_count=1,
    knowledge_boundary="ANSWERABLE",
    grounding_status="GROUNDED",
    verification_status="VERIFIED",
)
_assert(grounded_frame.confidence_band == expert.ExpertConfidenceBand.HIGH, f"grounded verified expert evidence should support HIGH band: {grounded_frame}")
_assert(grounded_frame.uncertainty_required is True, "verification-bounded expert decisions should still expose uncertainty requirement")
print("expert confidence band from grounding: PASS")


conflict_frame = expert.build_expert_response_frame(
    conflicted,
    evidence_sources_count=3,
    authoritative_sources_count=2,
    knowledge_boundary="CONFLICTING_KNOWLEDGE",
    grounding_status="PARTIALLY_GROUNDED",
    verification_status="INSUFFICIENT_EVIDENCE",
)
_assert(conflict_frame.confidence_band == expert.ExpertConfidenceBand.LOW, "conflicting evidence must remain LOW confidence")
_assert(conflict_frame.next_evidence_needed == ("resolve_conflicting_sources",), "conflict frame must request source reconciliation")
print("expert next-evidence frame: PASS")


public_frame = expert.public_expert_metadata(non_authoritative_high_stakes, non_authoritative_frame)
_assert(public_frame["response_frame"]["decision"] == "AUTHORITATIVE_EVIDENCE_REQUIRED", "public frame must expose safe boundary")
_assert(public_frame["response_frame"]["authoritative_sources_count"] == 0, "public frame must expose authority count")
_assert(public_frame["response_frame"]["next_evidence_needed"] == ["authoritative_source"], "public frame must expose next evidence safely")
_assert("matched_signals" not in public_frame, "response frame must not leak classifier markers")
print("public expert response frame: PASS")


domains = expert.supported_expert_domains()
_assert("GENERAL" in domains and "LOGISTICS" in domains and "SOFTWARE_ENGINEERING" in domains, "supported domains should be inspectable")
_assert(len(domains) == len(set(domains)), "supported domains should not contain duplicates")
print("expert domain registry: PASS")


print("SHY v0.20 EXPERT INTELLIGENCE CHECKPOINT 1: PASS")
