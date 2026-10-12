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

The RunPod vLLM worker exposes `/openai/v1/chat/completions` through its authenticated
queue-based endpoint. SHY limits requests to 512 generated tokens, one transport attempt,
180 seconds, and bounded text context. GPU startup and failed requests can also consume credits.
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
a fixture transport, routing isolation, missing configuration, error redaction, and token bounds.
It does not measure production accuracy or assert a cloud endpoint has answered.
