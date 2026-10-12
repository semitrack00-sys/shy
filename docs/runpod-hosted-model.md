# SHY hosted model connection

SHY supports an explicit RunPod backend in addition to the existing local Ollama backend.
It is not enabled by default and does not change the local Windows configuration.

Set these server-side environment variables on the hosted SHY service:

```
SHY_MODEL_BACKEND=runpod
SHY_RUNPOD_ENDPOINT_ID=<your-endpoint-id>
SHY_RUNPOD_API_KEY=<private-endpoint-inference-key>
SHY_RUNPOD_MODEL=qwen/qwen3.5-4b
```

Use the served model name from the endpoint, which can differ in capitalization from its
Hugging Face repository name. Credentials must never be added to Git, browser bundles,
NEXT_PUBLIC variables, or chat messages.

SHY submits one job to the authenticated `/run` queue endpoint using the vLLM worker's
OpenAI chat envelope, then polls `/status` for that same job. It waits up to 280 seconds
including GPU startup, bounds worker execution to 180 seconds, and sets a 285-second job
TTL. A failed wait attempts cancellation without submitting another job. Requests are
limited to 512 generated tokens and bounded text context. One request can be in flight per
SHY process; failures pause routing for 30 seconds before allowing another attempt. GPU startup and failed requests can also consume credits.
Use a maximum of one worker, zero active workers, five seconds of idle timeout, and an
execution timeout of 180 seconds. These scaling settings do not impose a dollar budget;
monitor spending independently. No automatic credit reload is configured by this change.

General chat goes to the explicitly configured hosted model. Requests classified as
local-only, private, or confidential cannot use this remote provider. Local document
generation and local reply-preference contexts retain their existing local-only policy;
they can be unavailable on the cloud host until an appropriate local engine exists.
Raw voice and image inference are not enabled by this adapter.

Health reports hosted inference as verified only after a successful response in the current
SHY process. Configuration alone is not proof of model readiness. Failed requests clear that
indicator. Ollama health fields continue to describe the local engine truthfully.

Validation: `python tests/test_runpod_provider.py` checks actual HTTP request construction with
a fixture transport, routing isolation, missing configuration, error redaction, token bounds, a simulated 264-second cold start, cancellation,
single-job concurrency, and recovery after repeated failures.
It does not measure production accuracy or assert a cloud endpoint has answered.


## Conversation quality (v0.105.25)

Runtime prompts name the actual executed adapter and model and supply the server UTC date
without implying access to current information. Guidance covers corrections, ambiguity,
language/format constraints, practical plans, uncertainty and truthful action claims. This
changes instructions and context handling; it does not upgrade the underlying 4B model.

The cloud follow-up checkbox is off by default, separate for each chat and reset on page
reload. Explicit `allow_cloud_history: true` permits up to 20 recent messages / 3,200
characters from that same owned conversation to be supplied to RunPod. This may include
private information typed or quoted in the thread. The path never retrieves durable memory
or another conversation. Local-only requests, document questions and private reply settings
retain local routing. Current-message privacy classification still applies. Without consent,
retrieved history keeps its existing local-only policy and may be unavailable on the host.
Model health refreshes after each completed or failed UI request.

Fixture checks cover consent defaults, thread isolation, context bounds, local-only behavior,
actual `/chat` integration and executed adapter facts. A small live synthetic test is useful
for spotting regressions but does not establish overall model accuracy or a measured quality
gain over the previous prompt.
