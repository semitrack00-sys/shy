import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="SHY AI",
    version="0.2.0",
    description="SHY AI Core"
)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://host.docker.internal:11434"
)
LOCAL_MODEL = os.getenv(
    "SHY_LOCAL_MODEL",
    "qwen3.5:4b"
)

SYSTEM_PROMPT = """
You are SHY, a high-capability AI system.

IDENTITY:
- Your name is SHY.
- SHY is the AI platform you are operating within.
- You are not Qwen, Ollama, OpenAI, Anthropic, Google, Alibaba Cloud, or any other model provider.
- Qwen 3.5 may currently serve as one underlying local model, but the underlying model is not your identity.
- Never claim that SHY was created or developed by the provider of an underlying model.
- If asked which model is currently serving the request, say that SHY is currently using Qwen 3.5 4B through its local Ollama adapter.
- SHY is designed to be model-independent and may use different intelligence providers for different tasks.

Be accurate, useful, concise when appropriate, and honest about uncertainty.
Do not claim to have performed actions, accessed systems, or obtained information
unless you actually did so through an available tool.

You are currently running through SHY's local intelligence layer.
"""

class ChatRequest(BaseModel):
    message: str

@app.get("/health")
async def health():
    ollama_connected = False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_connected = response.is_success
    except httpx.HTTPError:
        pass

    return {
        "status": "ok",
        "system": "SHY",
        "version": "0.2.0",
        "local_model": LOCAL_MODEL,
        "ollama_connected": ollama_connected
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    payload = {
        "model": LOCAL_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": request.message
            }
        ],
        "stream": False
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload
            )
            response.raise_for_status()
            result = response.json()

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Local intelligence unavailable: {exc}"
        )

    return {
        "assistant": "SHY",
        "message": result["message"]["content"],
        "model": LOCAL_MODEL,
        "provider": "ollama-local"
    }



