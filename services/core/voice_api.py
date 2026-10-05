"""Optional local Whisper HTTP adapter. Bounded PCM input; no audio persistence."""
from __future__ import annotations

import asyncio
import base64
import binascii
import io
import json
import os
import wave
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/voice", tags=["Local voice"])
MAX_BODY_BYTES = 1_400_000
MAX_AUDIO_BYTES = 960_044
MAX_SECONDS = 30
LANGUAGES = {"auto", "en", "fr", "ht", "es", "pt", "ko", "sw"}
_slot = asyncio.Semaphore(1)


class AudioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    audio_base64: str = Field(min_length=1, max_length=1_300_000)
    language: str = Field(default="auto", min_length=2, max_length=4)


def provider_url() -> str | None:
    raw = os.environ.get("SHY_WHISPER_URL", "").strip()
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
        valid = (parts.scheme == "http" and parts.hostname in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}
                 and not parts.username and not parts.password and parts.path in {"", "/"}
                 and not parts.query and not parts.fragment and parts.port is not None)
    except ValueError:
        valid = False
    return raw.rstrip("/") if valid else None


def validate_audio(encoded: str) -> tuple[bytes, float]:
    try:
        audio = base64.b64decode(encoded, validate=True)
        if len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(413, "voice_audio_byte_limit_exceeded")
        with wave.open(io.BytesIO(audio), "rb") as wav:
            frames = wav.getnframes()
            if (wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000
                    or wav.getcomptype() != "NONE" or not 0 < frames <= 16000 * MAX_SECONDS):
                raise ValueError("unsupported_pcm")
            if len(wav.readframes(frames)) != frames * 2:
                raise ValueError("truncated_pcm")
        return audio, frames / 16000
    except (ValueError, binascii.Error, wave.Error, EOFError):
        raise HTTPException(422, "voice_requires_complete_mono_16bit_16khz_pcm_wav_under_30_seconds") from None


async def transcribe_provider(url: str, audio: bytes, language: str) -> str:
    async with httpx.AsyncClient(timeout=httpx.Timeout(40, connect=3), follow_redirects=False, trust_env=False) as client:
        async with client.stream("POST", url + "/inference",
                                 data={"response_format": "json", "temperature": "0", "language": language},
                                 files={"file": ("speech.wav", audio, "audio/wav")}) as response:
            if response.status_code != 200:
                raise HTTPException(503, "local_speech_provider_refused_request")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > 65536:
                    raise HTTPException(502, "local_speech_provider_response_too_large")
    try:
        payload = json.loads(body)
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str) or len(text) > 8000:
            raise ValueError("invalid_transcript")
        return text.strip()
    except (ValueError, UnicodeError):
        raise HTTPException(502, "local_speech_provider_invalid_response") from None


@router.get("/status")
def voice_status():
    return {"configured": provider_url() is not None, "provider": "local_whisper_http",
            "provider_ready": None, "readiness": "not_probed", "max_seconds": MAX_SECONDS,
            "format": "mono_16bit_16khz_pcm_wav", "audio_persisted": False,
            "core_generates_speech": False, "configured_does_not_mean_verified": True}


@router.post("/transcribe")
async def transcribe(request: AudioRequest):
    url = provider_url()
    if url is None:
        raise HTTPException(503, "local_speech_provider_not_configured")
    if request.language not in LANGUAGES:
        raise HTTPException(422, "unsupported_speech_language")
    audio, duration = validate_audio(request.audio_base64)
    if _slot.locked():
        raise HTTPException(429, "local_speech_provider_busy")
    async with _slot:
        try:
            text = await asyncio.wait_for(transcribe_provider(url, audio, request.language), timeout=45)
        except (httpx.HTTPError, TimeoutError):
            raise HTTPException(503, "local_speech_provider_unavailable_or_timed_out") from None
    if not text:
        raise HTTPException(422, "no_speech_detected")
    return {"text": text, "duration_seconds": duration, "provider": "local_whisper_http",
            "audio_persisted": False, "chat_submitted": False, "approval_granted": False}


class VoiceBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST" or scope.get("path", "").rstrip("/") != "/voice/transcribe":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY_BYTES:
                await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"voice_request_byte_limit_exceeded"}'})
                return
            if not message.get("more_body", False):
                break
        try:
            text = body.decode("utf-8")
            depth, quoted, escaped = 0, False, False
            for char in text:
                if quoted:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        quoted = False
                elif char == '"':
                    quoted = True
                elif char in "[{":
                    depth += 1
                    if depth > 4:
                        raise ValueError("voice_json_depth_limit")
                elif char in "]}":
                    depth -= 1
            json.loads(text, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite_json")))
        except (ValueError, UnicodeError, RecursionError):
            await send({"type": "http.response.start", "status": 422, "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": b'{"detail":"invalid_voice_json"}'})
            return
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
