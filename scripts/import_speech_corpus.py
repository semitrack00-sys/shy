"""Prepare an offline Common Voice test split for SHY's real speech evaluator."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {"en", "fr", "ht"}


def read_split(directory: Path, limit: int):
    directory = directory.resolve(strict=True)
    split = (directory / "test.tsv").resolve(strict=True)
    if not split.is_relative_to(directory) or split.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("test_split_must_be_bounded_and_inside_dataset")
    selected, seen = [], set()
    with split.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not {"path", "sentence"}.issubset(reader.fieldnames or []):
            raise ValueError("test_split_requires_path_and_sentence")
        for index, row in enumerate(reader):
            if index >= 100_000:
                raise ValueError("test_split_row_limit")
            name, reference = row.get("path", ""), row.get("sentence", "")
            if (not name or not reference or len(reference) > 8000
                    or not 1 <= len(re.findall(r"\w+(?:'\w+)*", unicodedata.normalize("NFKC", reference).replace("’", "'"))) <= 200
                    or Path(name).name != name or name in seen):
                raise ValueError("invalid_or_duplicate_test_row")
            seen.add(name)
            audio = (directory / "clips" / name).resolve(strict=True)
            if (not audio.is_relative_to(directory / "clips") or not audio.is_file()
                    or audio.suffix.lower() not in {".mp3", ".wav", ".flac"}
                    or not 0 < audio.stat().st_size <= 10 * 1024 * 1024):
                raise ValueError("clip_must_be_bounded_and_inside_clips_directory")
            if len(selected) < limit:
                selected.append((audio, reference))
    if len(selected) != limit:
        raise ValueError("insufficient_test_split_cases")
    return selected


def convert_audio(source: Path, target: Path, ffmpeg: str):
    # Explicit demuxer and protocol restrictions prevent playlist/URL inputs.
    formats = {".mp3": "mp3", ".wav": "wav", ".flac": "flac"}
    subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-protocol_whitelist", "file,pipe", "-f", formats[source.suffix.lower()],
                    "-i", str(source), "-t", "31", "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", "-f", "wav", str(target)],
                   check=True, timeout=45, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Convert up to 31 seconds, then reject long clips instead of silently
    # truncating the recording while retaining its untruncated reference.
    if target.stat().st_size > 1_000_000:
        raise ValueError("converted_audio_too_large")
    with wave.open(str(target), "rb") as audio:
        frames = audio.getnframes()
        pcm = audio.readframes(frames)
        if (audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000
                or not 0 < frames <= 480_000 or len(pcm) != frames * 2):
            raise ValueError("clip_requires_complete_audio_under_30_seconds")
    # ffmpeg can add metadata chunks. Canonicalize to the 44-byte PCM header so
    # even a full 30-second recording fits the adapter's exact byte budget.
    with wave.open(str(target), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(pcm)


def import_corpus(datasets: dict[str, Path], output: Path, count: int, ffmpeg: str):
    if set(datasets) != LANGUAGES or not 3 <= count <= 30:
        raise ValueError("all_three_languages_and_three_to_30_cases_required")
    output = output.resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError("use_new_output_directory_outside_repository")
    # Validate all inputs before producing any output; no audio is downloaded.
    selected = {language: read_split(directory, count) for language, directory in datasets.items()}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".shy-speech-", dir=output.parent))
    cases, digests = [], set()
    try:
        for language in sorted(LANGUAGES):
            for index, (source, reference) in enumerate(selected[language], 1):
                case_id = f"{language}-{index:02d}"
                target = temporary / f"{case_id}.wav"
                convert_audio(source, target, ffmpeg)
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                if digest in digests:
                    raise ValueError("duplicate_audio_cannot_inflate_language_coverage")
                digests.add(digest)
                cases.append({"id": case_id, "language": language, "audio": target.name, "reference": reference})
        (temporary / "cases.json").write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
        # Move the complete corpus into place only after every conversion succeeds.
        if output.exists():
            raise ValueError("output_directory_already_exists")
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", action="append", required=True, metavar="LANG=EXTRACTED_DIRECTORY")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases-per-language", type=int, default=3)
    parser.add_argument("--ffmpeg", default="ffmpeg", help="Installed trusted ffmpeg executable")
    args = parser.parse_args()
    try:
        datasets = {}
        for item in args.dataset:
            language, directory = item.split("=", 1)
            if language in datasets or language not in LANGUAGES:
                raise ValueError("duplicate_or_unsupported_language")
            datasets[language] = Path(directory)
        executable = shutil.which(args.ffmpeg)
        if not executable:
            raise ValueError("ffmpeg_not_installed")
        count = import_corpus(datasets, args.output, args.cases_per_language, executable)
    except (ValueError, OSError, csv.Error, wave.Error, subprocess.SubprocessError):
        raise SystemExit("Corpus import failed; check all three local test splits, bounded recordings, new output location, and installed ffmpeg") from None
    print(json.dumps({"imported_cases": count, "downloaded_audio": False, "recognition_evaluated": False}))


if __name__ == "__main__":
    main()
