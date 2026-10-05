"""Local provider fixtures verify HTTP/audio boundaries, not acoustic accuracy."""
import base64
import importlib.util
import io
import os
import sys
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_voice_api", ROOT / "services/core/voice_api.py")
api = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = api
spec.loader.exec_module(api)
app = FastAPI()
app.include_router(api.router)
app.add_middleware(api.VoiceBodyLimit)


def wav_audio(rate=16000, channels=1, width=2, frames=1600):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(b"\0" * frames * channels * width)
    return buffer.getvalue()


class LocalVoiceTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"SHY_WHISPER_URL": "http://127.0.0.1:8178"})
        self.environment.start()
        self.client = TestClient(app)
        self.request = {"audio_base64": base64.b64encode(wav_audio()).decode(), "language": "en"}

    def tearDown(self):
        self.client.close()
        self.environment.stop()

    def test_provider_configuration_is_not_claimed_as_verified(self):
        status = self.client.get("/voice/status").json()
        self.assertTrue(status["configured"])
        self.assertIsNone(status["provider_ready"])
        self.assertFalse(status["audio_persisted"])

    def test_disabled_or_remote_provider_fails_closed(self):
        for url in ("", "https://example.com:443", "http://example.com:80", "http://user:secret@localhost:8178", "http://localhost:8178/redirect", "http://localhost:8178?token=secret"):
            with self.subTest(url=url), patch.dict(os.environ, {"SHY_WHISPER_URL": url}):
                self.assertFalse(self.client.get("/voice/status").json()["configured"])
                self.assertEqual(self.client.post("/voice/transcribe", json=self.request).status_code, 503)

    def test_valid_audio_returns_transcript_without_submitting_chat_or_approval(self):
        provider = AsyncMock(return_value="  Hello SHY  ")
        with patch.object(api, "transcribe_provider", provider):
            response = self.client.post("/voice/transcribe", json=self.request)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["text"], "  Hello SHY  ")
        self.assertFalse(response.json()["chat_submitted"])
        self.assertFalse(response.json()["approval_granted"])
        self.assertFalse(response.json()["audio_persisted"])
        provider.assert_awaited_once()
        self.assertEqual(provider.call_args.args[0], "http://127.0.0.1:8178")

    def test_rejects_invalid_audio_formats_truncation_and_duration(self):
        for audio in (b"not wav", wav_audio(rate=8000), wav_audio(channels=2), wav_audio(width=1),
                      wav_audio(frames=0), wav_audio()[:-4]):
            with self.subTest(size=len(audio)):
                result = self.client.post("/voice/transcribe", json={"audio_base64": base64.b64encode(audio).decode()})
                self.assertEqual(result.status_code, 422)
        audio = wav_audio(frames=480001)
        self.assertEqual(self.client.post("/voice/transcribe", json={"audio_base64": base64.b64encode(audio).decode()}).status_code, 413)

    def test_body_limit_invalid_json_and_unknown_fields(self):
        result = self.client.post("/voice/transcribe", content=iter([b'x' * 700000, b'x' * 700001]))
        self.assertEqual(result.status_code, 413)
        for raw in (b'{"audio_base64":"!"}', b'{"audio_base64":NaN}', b'[' * 20 + b']' * 20):
            self.assertEqual(self.client.post("/voice/transcribe", content=raw).status_code, 422)
        self.assertEqual(self.client.post("/voice/transcribe", json={**self.request, "url": "http://example.com"}).status_code, 422)

    def test_provider_timeout_empty_transcript_and_busy_boundaries(self):
        with patch.object(api, "transcribe_provider", AsyncMock(side_effect=httpx.ConnectError("private details"))):
            response = self.client.post("/voice/transcribe", json=self.request)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("private details", response.text)
        with patch.object(api, "transcribe_provider", AsyncMock(return_value="")):
            self.assertEqual(self.client.post("/voice/transcribe", json=self.request).status_code, 422)
        with patch.object(api, "_slot", SimpleNamespace(locked=lambda: True)):
            self.assertEqual(self.client.post("/voice/transcribe", json=self.request).status_code, 429)


class ProviderProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_whisper_multipart_contract_and_bounded_response(self):
        original_client = httpx.AsyncClient
        seen = []
        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"text": "Bonjour"})
        transport = httpx.MockTransport(handler)
        with patch.object(api.httpx, "AsyncClient", lambda **kwargs: original_client(transport=transport, **kwargs)):
            self.assertEqual(await api.transcribe_provider("http://127.0.0.1:8178", wav_audio(), "fr"), "Bonjour")
        self.assertEqual(str(seen[0].url), "http://127.0.0.1:8178/inference")
        self.assertIn(b'name="language"', seen[0].content)
        self.assertIn(b'filename="speech.wav"', seen[0].content)

    async def test_redirects_invalid_json_and_large_transcripts_fail(self):
        original_client = httpx.AsyncClient
        cases = [(httpx.Response(302, headers={"location": "http://example.com"}), 503),
                 (httpx.Response(200, content=b"not json"), 502),
                 (httpx.Response(200, json={"text": "x" * 8001}), 502),
                 (httpx.Response(200, content=b"x" * 65537), 502)]
        for response, status in cases:
            with self.subTest(status=status):
                transport = httpx.MockTransport(lambda request: response)
                with patch.object(api.httpx, "AsyncClient", lambda **kwargs: original_client(transport=transport, **kwargs)):
                    with self.assertRaises(api.HTTPException) as raised:
                        await api.transcribe_provider("http://localhost:8178", wav_audio(), "auto")
                self.assertEqual(raised.exception.status_code, status)


if __name__ == "__main__":
    unittest.main()
