"""Measure supplied English/French/Haitian Creole WAV cases against real local ASR."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import re
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/core"))
import voice_api
from fastapi import FastAPI
from fastapi.testclient import TestClient

REQUIRED_LANGUAGES = {"en", "fr", "ht"}


def words(text: str) -> list[str]:
    return re.findall(r"\w+(?:'\w+)*", unicodedata.normalize("NFKC", text).casefold().replace("’", "'"))


def edit_distance(reference: list[str], actual: list[str]) -> int:
    previous = list(range(len(actual) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, observed in enumerate(actual, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (expected != observed)))
        previous = current
    return previous[-1]


def load_cases(manifest_path: Path):
    if manifest_path.stat().st_size > 256 * 1024:
        raise ValueError("case_manifest_too_large")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list) or not 1 <= len(cases) <= 100:
        raise ValueError("one_to_100_cases_required")
    ids, digests, loaded = set(), set(), []
    directory = manifest_path.resolve().parent
    for case in cases:
        if (not isinstance(case, dict) or set(case) != {"id", "language", "audio", "reference"}
                or not isinstance(case["id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", case["id"])
                or case["id"] in ids or case["language"] not in REQUIRED_LANGUAGES
                or not isinstance(case["audio"], str) or not isinstance(case["reference"], str)
                or not 1 <= len(case["reference"]) <= 8000):
            raise ValueError("invalid_or_duplicate_case")
        reference = words(case["reference"])
        if not 1 <= len(reference) <= 200:
            raise ValueError("reference_requires_one_to_200_words")
        audio_path = (directory / case["audio"]).resolve()
        if not audio_path.is_relative_to(directory) or audio_path.stat().st_size > voice_api.MAX_AUDIO_BYTES:
            raise ValueError("audio_must_be_bounded_and_inside_case_directory")
        audio = audio_path.read_bytes()
        digest = hashlib.sha256(audio).hexdigest()
        if digest in digests:
            raise ValueError("duplicate_audio_cannot_inflate_language_coverage")
        encoded = base64.b64encode(audio).decode()
        _, duration = voice_api.validate_audio(encoded)
        ids.add(case["id"]); digests.add(digest)
        loaded.append((case["id"], case["language"], reference, encoded, duration, digest))
    return loaded


def evaluate_cases(cases, max_wer: float, min_cases: int):
    if not voice_api.provider_url():
        raise ValueError("permitted_local_provider_configuration_required")
    app = FastAPI(); app.include_router(voice_api.router); app.add_middleware(voice_api.VoiceBodyLimit)
    results = []
    with TestClient(app) as client:
        for case_id, language, reference, encoded, duration, digest in cases:
            start = time.monotonic()
            response = client.post("/voice/transcribe", json={"audio_base64": encoded, "language": language})
            elapsed = time.monotonic() - start
            text = response.json().get("text", "") if response.status_code == 200 else ""
            actual = words(text)
            if len(actual) > 500:
                raise ValueError("transcript_exceeds_evaluation_word_limit")
            edits = edit_distance(reference, actual) if response.status_code == 200 else None
            results.append({"id": case_id, "language": language, "audio_sha256": digest,
                            "http_status": response.status_code, "reference_words": len(reference),
                            "word_edits": edits, "wer": edits / len(reference) if edits is not None else None,
                            "seconds": round(elapsed, 3), "audio_seconds": duration,
                            "real_time_factor": round(elapsed / duration, 3)})
    languages = {}
    for language in sorted(REQUIRED_LANGUAGES):
        selected = [case for case in results if case["language"] == language]
        successful = [case for case in selected if case["word_edits"] is not None]
        count = sum(case["reference_words"] for case in successful)
        wer = sum(case["word_edits"] for case in successful) / count if count else None
        languages[language] = {"case_count": len(selected), "successful_cases": len(successful),
                               "corpus_wer": wer, "coverage_complete": len(selected) >= min_cases,
                               "passed": len(selected) >= min_cases and len(successful) == len(selected)
                               and wer is not None and wer <= max_wer}
    return {"passed": all(item["passed"] for item in languages.values()), "languages": languages,
            "cases": results, "max_wer_requested": max_wer, "min_cases_per_language": min_cases,
            "real_audio_inference": True, "gpu_verified": False,
            "representativeness_independently_verified": False,
            "full_transcripts_and_audio_stored_in_report": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--max-wer", type=float, required=True, help="Caller-selected acceptance threshold, not an established quality standard")
    parser.add_argument("--min-cases-per-language", type=int, default=3)
    parser.add_argument("--report", type=Path, default=Path(".validation/speech-evaluation.json"))
    args = parser.parse_args()
    if not math.isfinite(args.max_wer) or not 0 <= args.max_wer <= 1 or not 1 <= args.min_cases_per_language <= 30:
        raise SystemExit("Use finite max WER in [0,1] and minimum case count in [1,30]")
    try:
        report = evaluate_cases(load_cases(args.cases), args.max_wer, args.min_cases_per_language)
    except (ValueError, OSError, TypeError, KeyError, voice_api.HTTPException):
        raise SystemExit("Invalid corpus, audio, or local provider configuration; no quality result was produced") from None
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "languages": report["languages"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
