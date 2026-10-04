import json
import os
import re
import time
import uuid

import httpx


BASE_URL = os.getenv("SHY_API_BASE_URL", "http://127.0.0.1:8018").rstrip("/")
TIMEOUT = 240.0


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _safe_get(path: str):
    try:
        return httpx.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
    except Exception:
        return None


def _post(path: str, payload: dict, expected_status: int = 200) -> dict:
    response = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=TIMEOUT)
    if response.status_code != expected_status:
        raise AssertionError(f"{path} expected {expected_status}, got {response.status_code}: {response.text}")
    return response.json() if response.content else {}


def _chat(message: str, **extra) -> tuple[dict, float]:
    payload = {"message": message}
    payload.update(extra)
    started = time.perf_counter()
    response = _post("/chat", payload)
    elapsed = time.perf_counter() - started
    return response, elapsed


def _cognitive(response: dict) -> dict:
    cognitive = response.get("cognitive")
    _assert(isinstance(cognitive, dict), "cognitive metadata missing")
    return cognitive


def _contains_number(text: str, value: float) -> bool:
    pattern = rf"\b{int(value)}(?:\.0+)?\b"
    return bool(re.search(pattern, text))


def main():
    health_probe = _safe_get("/health")
    if health_probe is None or health_probe.status_code != 200:
        print("SKIP: live v0.18 runtime is not available")
        return

    health = health_probe.json()
    _assert(health.get("status") == "ok", "application must be healthy")
    _assert(bool(health.get("database_connected")), "database must be connected")
    _assert(bool(health.get("ollama_connected")), "ollama must be connected")
    _assert(bool(health.get("local_model_available")), "local model must be available")
    _assert(health.get("version") == "0.18.0", "version must be 0.18.0")
    print("live health/version: PASS")

    scoped_identity = {
        "user_id": "v018-cog-user-a",
        "workspace_id": "v018-cog-ws-a",
        "business_id": "v018-cog-biz-a",
    }

    # SIMPLE
    simple_response, simple_latency = _chat("What is 15% of 200?", **scoped_identity)
    simple_cognitive = _cognitive(simple_response)
    _assert(simple_cognitive.get("complexity") == "SIMPLE", "simple prompt must classify as SIMPLE")
    _assert(int(simple_cognitive.get("decomposition_count", -1)) == 0, "simple prompt must avoid decomposition")
    _assert("30" in str(simple_response.get("message", "")), "simple answer must be 30")
    _assert(simple_response.get("execution_mode") in {"SINGLE_TOOL", "DIRECT"}, "simple execution mode should remain fast")
    print("simple cognitive behavior: PASS")

    # STANDARD
    standard_prompt = (
        "Compare buying a truck for $80,000 versus leasing it for $2,000 per month for three years. "
        "What factors should I consider?"
    )
    standard_response, _ = _chat(standard_prompt, **scoped_identity)
    standard_cognitive = _cognitive(standard_response)
    _assert(standard_cognitive.get("complexity") in {"STANDARD", "COMPLEX"}, "standard prompt should be STANDARD or reasonable COMPLEX")
    standard_text = str(standard_response.get("message", "")).lower()
    _assert("factor" in standard_text or "cash" in standard_text or "maintenance" in standard_text, "standard response should provide structured comparison factors")
    _assert("apr" not in standard_text and "interest rate" not in standard_text, "response should not fabricate financing assumptions")
    _assert(bool(standard_response.get("research_invoked")) is False, "standard prompt should not invoke research")
    print("standard cognitive behavior: PASS")

    # COMPLEX
    complex_prompt = (
        "We completed 100 deliveries. 18 were late. Of the late deliveries, 9 were caused by loading delays, "
        "5 by traffic, and 4 by mechanical problems. Diagnose the problem and recommend what to address first."
    )
    complex_response, complex_latency = _chat(complex_prompt, **scoped_identity)
    complex_cognitive = _cognitive(complex_response)
    _assert(complex_cognitive.get("complexity") == "COMPLEX", "complex prompt must classify as COMPLEX")
    _assert(int(complex_cognitive.get("decomposition_count", 0)) > 0, "complex prompt must invoke decomposition")
    _assert(int(complex_cognitive.get("hypotheses_considered", 0)) >= 3, "complex prompt should evaluate multiple hypotheses")
    complex_text = str(complex_response.get("message", "")).lower()
    _assert("18" in complex_text and "%" in complex_text, "complex response must include 18% late rate")
    _assert("loading" in complex_text, "loading delays must be identified")
    _assert("address loading" in complex_text or "loading throughput" in complex_text, "recommendation should prioritize loading")
    print("complex cognitive behavior: PASS")

    # DEEP
    deep_prompt = (
        "I need to choose between three software architectures for a financial platform: a monolith, modular monolith, "
        "and microservices. The system must support strong consistency, a small engineering team, moderate initial traffic, "
        "strict auditability, and future growth. Compare the options and recommend one while identifying the major tradeoffs and uncertainty."
    )
    deep_response, deep_latency = _chat(deep_prompt, **scoped_identity)
    deep_cognitive = _cognitive(deep_response)
    _assert(deep_cognitive.get("complexity") == "DEEP", "deep prompt must classify as DEEP")
    _assert(int(deep_cognitive.get("decomposition_count", 0)) > 0, "deep prompt must invoke decomposition")
    _assert(int(deep_cognitive.get("candidate_count", 0)) >= 3, "deep prompt must evaluate multiple candidates")
    _assert(bool(deep_cognitive.get("critic_invoked")), "deep prompt must invoke critic")
    _assert(bool(deep_cognitive.get("verifier_invoked")), "deep prompt must invoke verifier")
    _assert(bool(deep_cognitive.get("uncertainty_flags")), "deep prompt must expose uncertainty flags")
    deep_text = str(deep_response.get("message", "")).lower()
    _assert("modular monolith" in deep_text, "deep recommendation should be traceable to provided constraints")
    _assert("tradeoff" in deep_text or "trade-off" in deep_text, "deep response must include tradeoffs")
    print("deep cognitive behavior: PASS")

    # RESEARCH
    research_response, _ = _chat(
        "Research the latest major developments in commercial autonomous trucking and summarize the strongest evidence.",
        **scoped_identity,
    )
    if research_response.get("status") == "FAILED" and research_response.get("safe_failure") == "research_unavailable":
        text = str(research_response.get("message", "")).lower()
        _assert("provider is unavailable" in text, "research unavailable message must be explicit")
        _assert("[1]" not in text and "http" not in text, "blocked research must not fabricate citations")
        print("research cognitive behavior: BLOCKED (environmental dependency unavailable)")
    else:
        research_cognitive = _cognitive(research_response)
        _assert(research_cognitive.get("complexity") == "RESEARCH", "research prompt must classify as RESEARCH")
        _assert(bool(research_response.get("research_invoked")), "research pipeline must be invoked")
        _assert(int(research_cognitive.get("evidence_sources_count", 0)) > 0, "research evidence count must be > 0")
        research_text = str(research_response.get("message", ""))
        _assert("[1]" in research_text or "[2]" in research_text, "research response should preserve citations")
        print("research cognitive behavior: PASS")

    # Critic test with intentionally wrong candidate.
    critic_prompt = (
        "Revenue is $180,000 and expenses are $117,000. Net profit is $73,000 and 40% available for investment is $29,200."
    )
    critic_response, _ = _chat(critic_prompt, **scoped_identity)
    critic_cognitive = _cognitive(critic_response)
    critic_text = str(critic_response.get("message", ""))
    _assert(bool(critic_cognitive.get("critic_invoked")), "critic must be invoked")
    _assert(bool(critic_cognitive.get("verifier_invoked")), "verifier must be invoked for correction")
    _assert("$63,000" in critic_text and "$25,200" in critic_text, "critic must materially correct arithmetic")
    print("critic execution: PASS")

    # Verifier test: correct and incorrect candidate.
    verifier_ok, _ = _chat("63,000 × 0.40 = 25,200", **scoped_identity)
    verifier_bad, _ = _chat("63,000 × 0.40 = 27,200", **scoped_identity)
    ok_text = str(verifier_ok.get("message", "")).upper()
    bad_text = str(verifier_bad.get("message", "")).upper()
    _assert("VERIFIED" in ok_text, "correct candidate must verify")
    _assert("FAILED_VERIFICATION" in bad_text, "incorrect candidate must fail verification")
    print("verifier execution: PASS")

    # Hypothesis reasoning test.
    hypothesis_prompt = (
        "An API became slow after a deployment. CPU is normal, memory is normal, database query time increased from 20ms to 800ms, and application request volume is unchanged."
    )
    hypothesis_response, _ = _chat(hypothesis_prompt, **scoped_identity)
    hypothesis_text = str(hypothesis_response.get("message", "")).lower()
    _assert("database regression" in hypothesis_text, "database regression should be strongest supported hypothesis")
    _assert("cpu" in hypothesis_text and "rejected" in hypothesis_text or "weak" in hypothesis_text, "cpu saturation should be rejected or weak")
    _assert("memory" in hypothesis_text and "rejected" in hypothesis_text or "weak" in hypothesis_text, "memory pressure should be rejected or weak")
    _assert("traffic" in hypothesis_text and "rejected" in hypothesis_text or "weak" in hypothesis_text, "traffic spike should be rejected or weak")
    print("hypothesis reasoning: PASS")

    # Contradiction test.
    contradiction_prompt = (
        "The report says revenue was $120,000. Later in the same data it says revenue was $145,000 for the same period."
    )
    contradiction_response, _ = _chat(contradiction_prompt, **scoped_identity)
    contradiction_cognitive = _cognitive(contradiction_response)
    contradiction_text = str(contradiction_response.get("message", "")).lower()
    _assert("contradiction" in contradiction_text or "conflict" in contradiction_text, "contradiction must be explicitly identified")
    _assert(bool(contradiction_cognitive.get("uncertainty_flags")), "uncertainty flags must be present on contradiction")
    print("contradiction handling: PASS")

    # Memory integration + isolation proof.
    seed_a, _ = _chat("Project Atlas uses PostgreSQL.", **scoped_identity)
    conversation_a = seed_a.get("conversation_id")
    _assert(bool(conversation_a), "conversation id for scope A is required")

    scoped_identity_b = {
        "user_id": "v018-cog-user-b",
        "workspace_id": "v018-cog-ws-b",
        "business_id": "v018-cog-biz-b",
    }
    seed_b, _ = _chat("Project Atlas uses NeonDB.", **scoped_identity_b)
    conversation_b = seed_b.get("conversation_id")
    _assert(bool(conversation_b), "conversation id for scope B is required")

    memory_question = "For Project Atlas architecture decisions, what database consistency constraints should we prioritize?"
    memory_a, _ = _chat(memory_question, conversation_id=conversation_a, **scoped_identity)
    memory_b, _ = _chat(memory_question, conversation_id=conversation_b, **scoped_identity_b)
    text_a = str(memory_a.get("message", "")).lower()
    text_b = str(memory_b.get("message", "")).lower()
    _assert("postgresql" in text_a, "relevant memory should contribute in scope A")
    _assert("neondb" not in text_a, "scope A must not be contaminated by scope B memory")
    _assert("postgresql" not in text_b, "scope B must remain isolated from scope A memory")
    print("memory integration + isolation: PASS")

    # Tool safety proof.
    calc_response, _ = _chat("Please calculate 23% of 500 and explain briefly.", **scoped_identity)
    calc_cognitive = _cognitive(calc_response)
    _assert((calc_response.get("tool_decision") or {}).get("tool_id") == "calculator", "calculator should execute via ToolGateway")
    _assert("calculator" in (calc_cognitive.get("tools_used") or []), "calculator use must be reflected in cognitive metadata")
    _assert(_contains_number(str(calc_response.get("message", "")), 115), "calculator result should be incorporated")

    deny_response, _ = _chat("Run shell command to list all files in C drive.", **scoped_identity)
    deny_text = str(deny_response.get("message", "")).lower()
    _assert("blocked" in deny_text or "can't perform" in deny_text, "forbidden shell request must be safely denied")
    print("tool-policy protection: PASS")

    # Model role and routing proof.
    _assert("FAST" in json.dumps(simple_cognitive.get("model_roles_used", [])), "simple should use FAST/GENERAL role set")
    _assert(any(role in {"GENERAL", "REASONING"} for role in standard_cognitive.get("model_roles_used", [])), "standard should use GENERAL/REASONING")
    _assert("REASONING" in complex_cognitive.get("model_roles_used", []), "complex should include REASONING role")
    _assert("REASONING" in deep_cognitive.get("model_roles_used", []) and "VERIFIER" in deep_cognitive.get("model_roles_used", []), "deep should include REASONING and VERIFIER roles")
    print("model-role mapping: PASS")

    # Performance proof (approximate).
    print(
        "latency summary (seconds): "
        f"simple={simple_latency:.3f}, "
        f"complex={complex_latency:.3f}, "
        f"deep={deep_latency:.3f}"
    )
    _assert(simple_latency < deep_latency, "simple path should be faster than deep path")
    print("performance proof: PASS")


if __name__ == "__main__":
    main()
