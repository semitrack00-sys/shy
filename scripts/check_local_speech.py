"""Run one real acoustic smoke check against the configured local Whisper adapter."""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/core"))
import voice_api
from fastapi import FastAPI
from fastapi.testclient import TestClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--language", choices=sorted(voice_api.LANGUAGES), default="en")
    parser.add_argument("--expected-substring", required=True)
    parser.add_argument("--report", type=Path, default=Path(".validation/local-speech-smoke.json"))
    args = parser.parse_args()
    if not voice_api.provider_url():
        raise SystemExit("Configure a permitted SHY_WHISPER_URL before running this check")
    audio = args.audio.read_bytes()
    encoded = base64.b64encode(audio).decode()
    voice_api.validate_audio(encoded)
    app = FastAPI()
    app.include_router(voice_api.router)
    app.add_middleware(voice_api.VoiceBodyLimit)
    with TestClient(app) as client:
        start = time.monotonic()
        response = client.post("/voice/transcribe", json={"audio_base64": encoded, "language": args.language})
    passed = response.status_code == 200 and args.expected_substring.casefold() in response.json().get("text", "").casefold()
    # Do not store the acoustic file, full transcript, or provider address in the report.
    report = {"passed": passed, "real_audio_inference": True, "fixture_transcription": False,
              "language": args.language, "seconds": round(time.monotonic() - start, 3),
              "http_status": response.status_code, "gpu_verified": False,
              "scope": "one_acoustic_smoke_case_not_a_quality_benchmark"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
