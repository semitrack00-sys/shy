import json
import os
import re

import httpx


BASE_URL = os.getenv("SHY_API_BASE_URL", "http://127.0.0.1:8016").rstrip("/")
TIMEOUT = 180.0


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _get(path: str) -> dict:
    response = httpx.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _safe_get(path: str):
    try:
        response = httpx.get(f"{BASE_URL}{path}", timeout=TIMEOUT)
        return response
    except Exception:
        return None


def _post(path: str, payload: dict, expected_status: int = 200) -> dict:
    response = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=TIMEOUT)
    if response.status_code != expected_status:
        raise AssertionError(f"{path} expected {expected_status}, got {response.status_code}: {response.text}")
    if response.content:
        return response.json()
    return {}


def _state() -> dict:
    return _get("/testing/model-routing-state")


def _reset_state():
    _post("/testing/model-routing/reset", {})


def _configure(provider_id: str, mode: str = "ok", health: str | None = None):
    payload = {"provider_id": provider_id, "mode": mode}
    if health is not None:
        payload["health"] = health
    _post("/testing/model-routing/provider", payload)


def _chat(message: str, local_only: bool = False, disable_memory_context: bool = True) -> dict:
    payload = {
        "message": message,
        "local_only": local_only,
        "testing_disable_memory_context": disable_memory_context,
    }
    return _post("/chat", payload)


def _chat_fail(message: str, local_only: bool = False, expected_status: int = 503, disable_memory_context: bool = True) -> dict:
    response = httpx.post(
        f"{BASE_URL}/chat",
        json={
            "message": message,
            "local_only": local_only,
            "testing_disable_memory_context": disable_memory_context,
        },
        timeout=TIMEOUT,
    )
    _assert(response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}")
    return response.json()


def _routing_consistent(response: dict):
    routing = response.get("model_routing") or {}
    _assert(routing.get("selection_matches_execution") is True, "selection/execution mismatch")
    _assert(routing.get("selected_provider") == routing.get("executed_provider"), "provider mismatch")
    _assert(routing.get("selected_model") == routing.get("executed_model"), "model mismatch")


def _provider_call_delta(before: dict, after: dict, provider_id: str) -> int:
    b = int((before.get("providers", {}).get(provider_id, {}) or {}).get("call_count", 0))
    a = int((after.get("providers", {}).get(provider_id, {}) or {}).get("call_count", 0))
    return a - b


def _local_call_delta(before: dict, after: dict) -> int:
    b = int((before.get("local_provider_stats", {}) or {}).get("call_count", 0))
    a = int((after.get("local_provider_stats", {}) or {}).get("call_count", 0))
    return a - b


def _citation_markers(text: str) -> set[str]:
    return set(re.findall(r"\[(\d+)\]", text or ""))


def main():
    probe = _safe_get("/health")
    if probe is None or probe.status_code != 200:
        print("SKIP: live model routing endpoint is not available")
        return

    health = _get("/health")
    _assert(health.get("version") in {"0.16.0", "0.17.0"}, "version must be 0.16.0 or 0.17.0")
    _assert(bool(health.get("ollama_connected")), "ollama must be connected")
    _assert(bool(health.get("database_connected")), "database must be connected")
    _assert("durable_memory" in health, "durable memory diagnostics missing")
    _assert("model_routing" in health, "model routing diagnostics missing")
    lowered = json.dumps(health).lower()
    for marker in ("password", "api_key", "authorization", "bearer", "token="):
        _assert(marker not in lowered, f"health leaked sensitive marker: {marker}")
    print("health/version: PASS")

    _reset_state()

    # Local-only baseline.
    before = _state()
    local_response = _chat("Summarize why bounded retries are useful.", local_only=True)
    after = _state()
    _assert(local_response.get("status") == "RESPOND", "local-only request should respond")
    _routing_consistent(local_response)
    local_routing = local_response["model_routing"]
    _assert(local_routing.get("reason_code") == "LOCAL_PRIVACY", "local-only reason must be LOCAL_PRIVACY")
    _assert(local_routing.get("selected_provider") == "ollama", "local-only provider must be ollama")
    _assert(local_routing.get("selected_model") == "qwen3.5:4b", "local-only model must be qwen3.5:4b")
    _assert(local_routing.get("fallback_used") is False, "local-only should not fallback")
    _assert(_provider_call_delta(before, after, "fake_reasoning") == 0, "external provider must not be called")
    _assert(_provider_call_delta(before, after, "fake_frontier") == 0, "external provider must not be called")
    _assert(_local_call_delta(before, after) >= 1, "local execution counter should increment")
    print("local-only baseline: PASS")

    # Actual external-provider execution.
    _reset_state()
    _configure("fake_reasoning", "ok", "HEALTHY")
    _configure("fake_frontier", "ok", "HEALTHY")
    _configure("fake_fast", "ok", "HEALTHY")
    _configure("ollama", "ok", "UNAVAILABLE")
    before = _state()
    reasoning_response = _chat("Research the latest major developments in battery technology.")
    after = _state()
    _assert(reasoning_response.get("status") == "RESPOND", "reasoning response expected")
    _assert(reasoning_response.get("execution_mode") == "RESEARCH", "external proof should run via research mode")
    _assert(reasoning_response.get("research_invoked") is True, "external proof should invoke research pipeline")
    _routing_consistent(reasoning_response)
    rr = reasoning_response["model_routing"]
    _assert(rr.get("selected_provider") != "ollama", "external provider should be selected for this proof")
    _assert(rr.get("role") == "RESEARCH", "research role expected for external execution proof")
    _assert(_provider_call_delta(before, after, rr.get("selected_provider")) == 1, "selected provider should execute exactly once")
    _assert(_local_call_delta(before, after) == 0, "local provider should not execute on external research synthesis success")
    _assert(reasoning_response.get("provider") == rr.get("executed_provider"), "public provider should reflect actual executor")
    print("actual external-provider execution: PASS")

    # One-fallback success via timeout on preferred provider.
    _reset_state()
    _configure("fake_reasoning", "ok", "HEALTHY")
    _configure("fake_frontier", "ok", "HEALTHY")
    _configure("fake_fast", "ok", "HEALTHY")
    _configure("ollama", "ok", "UNAVAILABLE")

    probe_prompt = "Research the latest major developments in battery technology."
    probe = _chat(probe_prompt)
    _assert(probe.get("status") == "RESPOND", "probe request should respond")
    preferred_provider = (probe.get("model_routing") or {}).get("selected_provider")
    _assert(bool(preferred_provider), "probe must provide selected provider")
    _assert(preferred_provider != "ollama", "probe should select a remote provider")

    _configure(preferred_provider, "timeout", "HEALTHY")

    before = _state()
    fallback_response = _chat(probe_prompt)
    after = _state()
    _assert(fallback_response.get("status") == "RESPOND", "fallback response expected")
    _routing_consistent(fallback_response)
    fr = fallback_response["model_routing"]
    _assert(fr.get("fallback_used") is True, "fallback_used should be true")
    _assert(fr.get("reason_code") == "FALLBACK_PROVIDER", "fallback reason expected")
    _assert(_provider_call_delta(before, after, preferred_provider) == 1, "primary should be called once")
    _assert(_provider_call_delta(before, after, fr.get("selected_provider")) >= 1, "fallback provider should execute")
    total_attempts = (
        _provider_call_delta(before, after, "fake_reasoning")
        + _provider_call_delta(before, after, "fake_frontier")
        + _provider_call_delta(before, after, "fake_fast")
        + _local_call_delta(before, after)
    )
    _assert(total_attempts <= 3, "attempts must stay bounded to 3")
    health_state = after.get("provider_health", {})
    _assert(health_state.get(preferred_provider) in {"DEGRADED", "UNAVAILABLE"}, "failed provider should degrade")
    print("one-fallback success + bounded attempts: PASS")

    # Empty-response recovery.
    _reset_state()
    _configure("fake_reasoning", "empty", "HEALTHY")
    _configure("fake_frontier", "ok", "HEALTHY")
    empty_response = _chat("Compare three fault-tolerant payment architectures.")
    _assert(empty_response.get("status") == "RESPOND", "empty-response recovery should respond")
    _routing_consistent(empty_response)
    _assert(bool(str(empty_response.get("message", "")).strip()), "empty output must never reach user")
    _assert(empty_response.get("hidden_reasoning_exposed") is False, "hidden reasoning must stay hidden")
    print("empty-response recovery: PASS")

    # Malformed-response recovery.
    _reset_state()
    _configure("fake_reasoning", "malformed", "HEALTHY")
    _configure("fake_frontier", "ok", "HEALTHY")
    malformed_response = _chat("Compare three fault-tolerant payment architectures.")
    _assert(malformed_response.get("status") == "RESPOND", "malformed-response recovery should respond")
    _routing_consistent(malformed_response)
    print("malformed-response recovery: PASS")

    # Timeout recovery.
    _reset_state()
    _configure("fake_reasoning", "timeout", "HEALTHY")
    _configure("fake_frontier", "ok", "HEALTHY")
    timeout_response = _chat("Compare three fault-tolerant payment architectures.")
    _assert(timeout_response.get("status") == "RESPOND", "timeout recovery should respond")
    _routing_consistent(timeout_response)
    print("timeout recovery: PASS")

    # All providers fail.
    _reset_state()
    _configure("fake_reasoning", "timeout", "HEALTHY")
    _configure("fake_frontier", "malformed", "HEALTHY")
    _configure("fake_fast", "error", "HEALTHY")
    _configure("fake_coding", "error", "HEALTHY")
    _configure("ollama", "timeout")
    before = _state()
    failure = _chat_fail("Compare three fault-tolerant payment architectures.")
    after = _state()
    safe_detail = str(failure.get("detail", "")).lower()
    _assert("traceback" not in safe_detail and "http://" not in safe_detail and "https://" not in safe_detail, "failure leaked unsafe details")
    total_attempts = (
        _provider_call_delta(before, after, "fake_reasoning")
        + _provider_call_delta(before, after, "fake_frontier")
        + _local_call_delta(before, after)
    )
    _assert(total_attempts <= 3, "all-fail attempts must be bounded to 3")
    print("all-provider-failure handling: PASS")

    # Role validation via live execution.
    _reset_state()
    _configure("fake_reasoning", "ok", "HEALTHY")
    _configure("fake_frontier", "ok", "HEALTHY")
    _configure("fake_coding", "ok", "HEALTHY")
    _configure("ollama", "ok")

    fast = _chat("Reply with exactly: PING")
    _assert(fast.get("status") == "RESPOND", "FAST request should respond")
    _routing_consistent(fast)
    _assert(fast.get("model_routing", {}).get("role") in {"FAST", "GENERAL"}, "FAST/GENERAL role expected")
    print("FAST/GENERAL route: PASS")

    reasoning = _chat("Compare three fault-tolerant payment architectures.")
    _assert(reasoning.get("status") == "RESPOND", "reasoning request should respond")
    _routing_consistent(reasoning)
    _assert(reasoning.get("model_routing", {}).get("role") == "REASONING", "REASONING role expected")
    print("REASONING route: PASS")

    coding = _chat("Find the bug in this Python function: def add(a,b): return a-b")
    _assert(coding.get("status") == "RESPOND", "coding request should respond")
    _routing_consistent(coding)
    _assert(coding.get("model_routing", {}).get("role") == "CODING", "CODING role expected")
    print("CODING route: PASS")

    # Real research evidence + synthesis routing proof.
    _reset_state()
    _configure("fake_reasoning", "ok", "HEALTHY")
    _configure("fake_frontier", "ok", "HEALTHY")
    _configure("fake_fast", "ok", "HEALTHY")
    _configure("ollama", "ok", "UNAVAILABLE")

    research_prompt = "Research the latest major developments in battery technology."
    before_research = _state()
    research = _chat(research_prompt)
    after_research = _state()

    if research.get("status") != "RESPOND":
        _assert(research.get("safe_failure") == "research_unavailable", "unexpected research failure shape")
        print("RESEARCH LIVE EVIDENCE: BLOCKED")
    else:
        _assert(research.get("execution_mode") == "RESEARCH", "research execution mode expected")
        _assert(research.get("research_invoked") is True, "research should be invoked")
        _assert(research.get("hidden_reasoning_exposed") is False, "hidden reasoning must not be exposed")
        _routing_consistent(research)

        research_routing = research.get("model_routing") or {}
        _assert(research_routing.get("role") == "RESEARCH", "RESEARCH role expected")
        _assert(bool(research_routing.get("selected_provider")), "selected synthesis provider missing")
        _assert(bool(research_routing.get("selected_model")), "selected synthesis model missing")

        citation_set_baseline = _citation_markers(str(research.get("message", "")))
        _assert(len(citation_set_baseline) > 0, "citations must be retained in research answer")

        baseline_provider = str(research_routing.get("executed_provider"))
        baseline_stats = (after_research.get("providers", {}) or {}).get(baseline_provider, {})
        baseline_summary = baseline_stats.get("last_request_summary", {})
        baseline_evidence_items = int(baseline_summary.get("evidence_item_count", 0))
        baseline_evidence_fingerprint = str(baseline_summary.get("evidence_fingerprint", ""))
        _assert(baseline_evidence_items > 0, "research evidence count must be > 0")
        _assert(bool(baseline_evidence_fingerprint), "research evidence fingerprint missing")

        # Provider-health/fallback proof for RESEARCH synthesis.
        preferred_provider = str(research_routing.get("selected_provider"))
        _assert(preferred_provider != "ollama", "research proof expects external synthesis provider")

        health_before = (before_research.get("provider_health", {}) or {}).get(preferred_provider)
        _assert(health_before in {"HEALTHY", "UNKNOWN"}, "research synthesis provider should start healthy/unknown")

        _configure(preferred_provider, "timeout", "HEALTHY")
        before_fallback = _state()
        research_fallback = _chat(research_prompt)
        after_fallback = _state()

        _assert(research_fallback.get("status") == "RESPOND", "research fallback should still respond")
        _assert(research_fallback.get("execution_mode") == "RESEARCH", "research fallback execution mode expected")
        _assert(research_fallback.get("research_invoked") is True, "research must still be invoked")
        _assert(research_fallback.get("hidden_reasoning_exposed") is False, "hidden reasoning must not be exposed")
        _routing_consistent(research_fallback)

        fallback_routing = research_fallback.get("model_routing") or {}
        _assert(fallback_routing.get("role") == "RESEARCH", "RESEARCH role expected on fallback")
        _assert(fallback_routing.get("fallback_used") is True, "fallback_used should be true for research synthesis")
        _assert(fallback_routing.get("reason_code") == "FALLBACK_PROVIDER", "fallback reason expected")

        fallback_provider = str(fallback_routing.get("executed_provider"))
        _assert(fallback_provider != preferred_provider, "fallback provider should differ from failed preferred provider")

        total_model_attempts = (
            _provider_call_delta(before_fallback, after_fallback, "fake_reasoning")
            + _provider_call_delta(before_fallback, after_fallback, "fake_frontier")
            + _provider_call_delta(before_fallback, after_fallback, "fake_fast")
            + _local_call_delta(before_fallback, after_fallback)
        )
        _assert(total_model_attempts <= 3, "research synthesis attempts must stay bounded to 3")

        citation_set_fallback = _citation_markers(str(research_fallback.get("message", "")))
        _assert(len(citation_set_fallback) > 0, "fallback research answer must retain citations")

        fallback_stats = (after_fallback.get("providers", {}) or {}).get(fallback_provider, {})
        fallback_summary = fallback_stats.get("last_request_summary", {})
        _assert(int(fallback_summary.get("evidence_item_count", 0)) > 0, "fallback evidence count must be > 0")
        _assert(str(fallback_summary.get("evidence_fingerprint", "")) == baseline_evidence_fingerprint, "evidence set changed during synthesis fallback")

        health_after_failure = (after_fallback.get("provider_health", {}) or {}).get(preferred_provider)
        _assert(health_after_failure in {"DEGRADED", "UNAVAILABLE"}, "failed research provider should degrade")

        # Recovery to healthy.
        _configure(preferred_provider, "ok", "HEALTHY")
        post_recovery_state = _state()
        _assert((post_recovery_state.get("provider_health", {}) or {}).get(preferred_provider) == "HEALTHY", "research provider should recover to HEALTHY")

        print("RESEARCH route: PASS")

    _reset_state()
    _configure("fake_reasoning", "ok", "HEALTHY")
    _configure("fake_frontier", "ok", "HEALTHY")
    _configure("fake_fast", "ok", "HEALTHY")
    _configure("fake_coding", "ok", "HEALTHY")
    _configure("ollama", "ok", "HEALTHY")

    verifier = _chat("Design a fault-tolerant payment processing architecture and explain major tradeoffs.")
    _assert(verifier.get("status") == "RESPOND", "verifier scenario should respond")
    _assert(verifier.get("adaptive_mode") == "verify", "verify mode expected")
    _routing_consistent(verifier)
    verifier_role = verifier.get("model_routing", {}).get("role")
    _assert(verifier_role in {"VERIFIER", "REASONING"}, "Verifier flow must report VERIFIER or REASONING role")
    print("VERIFIER behavior: PASS")

    multistep = _chat("Check SHY's health and tell me what percentage of its required services are connected.")
    _assert(multistep.get("status") == "RESPOND", "MULTI_STEP request should respond")
    _assert(multistep.get("execution_mode") == "MULTI_STEP", "MULTI_STEP mode expected")
    planner_meta = multistep.get("model_routing") or {}
    if planner_meta:
        _assert(planner_meta.get("role") in {"PLANNER", "FAST", "GENERAL", "REASONING"}, "Unexpected planner-route metadata role")
    print("PLANNER behavior: PASS")

    # Memory safety through external provider capture metadata.
    _reset_state()
    _configure("fake_reasoning", "ok", "HEALTHY")
    _configure("fake_frontier", "ok", "HEALTHY")
    _configure("ollama", "ok")

    _chat("My company is called Alpha Logistics.", disable_memory_context=False)
    _chat("My company is now called Beta Logistics, not Alpha Logistics.", disable_memory_context=False)

    memory_response = None
    summary = {}
    for memory_prompt in (
        "Compare migration tradeoffs using my company context.",
        "What is my company name now?",
        "Use my saved company context to suggest one migration risk.",
    ):
        memory_response = _chat(memory_prompt, disable_memory_context=False)
        _assert(memory_response.get("status") == "RESPOND", "memory-context request should respond")
        _routing_consistent(memory_response)
        state_after_memory = _state()
        executed_provider = (memory_response.get("model_routing") or {}).get("executed_provider")
        provider_stats = (state_after_memory.get("providers", {}) or {}).get(executed_provider, {})
        summary = provider_stats.get("last_request_summary", {})
        if bool(summary.get("has_memory_context")):
            break

    if summary:
        _assert(summary.get("contains_secret_marker") is False, "secret markers must be excluded")
        _assert(summary.get("contains_hidden_reasoning_marker") is False, "hidden reasoning markers must be excluded")
        _assert(summary.get("contains_superseded_marker") is False, "superseded markers must be excluded")
    _assert(memory_response.get("hidden_reasoning_exposed") is False, "hidden reasoning must remain hidden")
    print("memory safety: PASS")

    # Tool path preservation.
    _reset_state()
    before = _state()
    tool_response = _chat("What is 17% of 842?")
    after = _state()
    _assert(tool_response.get("adaptive_mode") == "tool", "calculator request should use tool mode")
    _assert(tool_response.get("tool_selected") == "calculator", "calculator tool should be selected")
    _assert("143.14" in str(tool_response.get("message", "")), "calculator result mismatch")
    fake_calls = sum(int((stats or {}).get("call_count", 0)) for stats in (after.get("providers", {}) or {}).values())
    fake_calls_before = sum(int((stats or {}).get("call_count", 0)) for stats in (before.get("providers", {}) or {}).values())
    _assert(fake_calls == fake_calls_before, "tool path should not invoke external model execution")
    _assert(_local_call_delta(before, after) == 0, "tool path should not invoke local model execution")
    print("tool path preservation: PASS")

    print("routing-selected == actual-executed: PASS")

    print("SHY v0.16 live model-routing integration: PASS")


if __name__ == "__main__":
    main()
