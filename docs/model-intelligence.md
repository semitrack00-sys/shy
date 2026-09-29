# SHY Model Intelligence Architecture (Phase 6A)

## SHY Identity
SHY is the intelligence platform.
Model providers are replaceable resources behind SHY contracts.

The local Qwen model through Ollama remains supported, but it is one model option, not SHY's intelligence ceiling.

## Provider Contract
Provider adapters implement a common interface:

- `provider_id`
- `health()`
- `list_models()`
- `generate(request, model_id)`

Provider adapters must not query SHY memory directly and must not expose hidden reasoning.

## Core Contracts
`services/model-router/app/contracts.py` defines:

- capability enum (`CHAT`, `REASONING`, `DEEP_REASONING`, `CODING`, `RESEARCH_SYNTHESIS`, ...)
- `ModelProfile`
- `ModelRequest`
- `ModelResponse`
- privacy/cost/latency/quality classes
- provider health and structured failure categories
- structured selection decision and orchestration result contracts

## Model Registry
`services/model-router/app/registry.py`:

- registers providers and model profiles
- rejects duplicate provider/model IDs
- filters enabled/capable models
- reports provider health
- preserves deterministic ordering

## Selection Policy
`services/model-router/app/selection.py`:

- selects models by capability and policy inputs
- enforces privacy constraints
- excludes unavailable providers
- supports deterministic ranking
- returns structured `selection_reason_code`

## Orchestrator
`services/model-router/app/orchestrator.py`:

- performs bounded selection + provider call
- validates response shape/content
- applies bounded fallback attempts
- returns terminal structured failure on exhaustion

No uncontrolled retries or recursive loops are allowed.

## Local Ollama Role
`services/model-router/app/providers/ollama.py` keeps local compatibility:

- provider: `ollama`
- model: `qwen3.5:4b` (configurable)
- local privacy-friendly option

## Fake Providers (Test Only)
`services/model-router/app/providers/fake.py` provides deterministic offline test providers:

- `fake_fast`
- `fake_frontier`
- `fake_reasoning`
- `fake_coding`

These providers are for deterministic testing and are not presented as real vendors.

## Router Integration
`services/model-router/app/router.py` integrates with existing intelligence classification and maps capability requirements to model-capability selection.

The router keeps existing route output shape while using policy-driven model selection internally.

## Privacy, Fallback, Escalation
Phase 6A enforces:

- `LOCAL_ONLY` requests stay local
- fallback candidates must satisfy required capability
- bounded attempts and bounded escalation
- fail-closed behavior when no capable model is available

## Security Boundary
Model selection never grants execution authority.
Tool execution remains controlled by SHY ToolGateway, permission policy, and approval tokens.

## Future Real Providers
Real frontier adapters can be added later through the same provider interface.
Phase 6A does not include real cloud API integration, API keys, or billing.

## Phase 6B Preparation
The architecture prepares for:

- richer memory-conditioned requests (memory context passed into `ModelRequest`)
- stronger coding-specialist routing
- verification-driven retry/fallback/escalation policies
- multi-model critique/repair flows with bounded control
