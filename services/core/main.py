import os
import uuid

import httpx
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from model_router.router import ModelRouter

from memory import (
    conversation_exists,
    create_conversation,
    ensure_default_user,
    load_messages,
    save_message,
)

app = FastAPI(
    title="SHY AI",
    version="0.5.0",
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

router = ModelRouter(LOCAL_MODEL)

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
    conversation_id: uuid.UUID | None = None


@app.on_event("startup")
def startup():
    try:
        ensure_default_user()
    except psycopg.Error as exc:
        raise RuntimeError(
            f"SHY database initialization failed: {exc}"
        ) from exc


@app.get("/health")
async def health():
    ollama_connected = False
    database_connected = False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_connected = response.is_success
    except httpx.HTTPError:
        pass

    try:
        ensure_default_user()
        database_connected = True
    except psycopg.Error:
        pass

    return {
        "status": "ok",
        "system": "SHY",
        "version": "0.5.0",
        "local_model": LOCAL_MODEL,
        "ollama_connected": ollama_connected,
        "database_connected": database_connected,
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        if request.conversation_id is None:
            conversation_id = create_conversation()
        else:
            conversation_id = request.conversation_id

            if not conversation_exists(conversation_id):
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found."
                )

        history = load_messages(conversation_id)

    except HTTPException:
        raise

    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail=f"SHY memory unavailable: {exc}"
        )

    route = router.route(request.message)

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    for item in history:
        messages.append(
            {
                "role": item["role"],
                "content": item["content"],
            }
        )

    messages.append(
        {
            "role": "user",
            "content": request.message,
        }
    )

    try:
        save_message(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
        )

    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail=f"SHY memory unavailable: {exc}"
        )

    payload = {
        "model": route.model,
        "messages": messages,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Local intelligence unavailable: {exc}"
        )

    assistant_message = result["message"]["content"]

    try:
        save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_message,
            model=route.model,
            provider=route.provider,
            task_type=route.task_type,
        )

    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail=f"SHY response generated but memory save failed: {exc}"
        )

    return {
        "assistant": "SHY",
        "message": assistant_message,
        "conversation_id": str(conversation_id),
        "model": route.model,
        "provider": route.provider,
        "task_type": route.task_type,
        "routing_reason": route.reason,
    }
