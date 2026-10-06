"""Verify a running SHY release over HTTP without generating chat or changing data."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class VerificationError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def request_json(base_url, path, payload=None, expected_status=200):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(base_url + path, data=data, headers={"Content-Type": "application/json"})
    # Local checks must not leak supplied examples to a configured proxy or redirect.
    opener = build_opener(ProxyHandler({}), NoRedirects())
    try:
        response = opener.open(request, timeout=10)
    except HTTPError as exc:
        response = exc
    with response:
        require(response.code == expected_status, f"{path}: expected HTTP {expected_status}, got {response.code}")
        raw = response.read(1024 * 1024 + 1)
        require(len(raw) <= 1024 * 1024, f"{path}: oversized response")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise VerificationError(f"{path}: invalid JSON response") from exc


def verify(base_url, examples_path, expected_version="0.105.6", wait_seconds=60, require_model=False):
    parts = urlsplit(base_url)
    require(parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}
            and not parts.username and not parts.password and parts.path in {"", "/"}
            and not parts.query and not parts.fragment, "Use a loopback HTTP URL, e.g. http://127.0.0.1:8000")
    base_url = base_url.rstrip("/")
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            health = request_json(base_url, "/health")
            break
        except (URLError, TimeoutError, ConnectionError):
            if time.monotonic() >= deadline:
                raise VerificationError("SHY did not become reachable before the readiness deadline")
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    require(isinstance(health, dict), "Health response must be an object")
    require(health.get("version") == expected_version, "Running SHY version does not match the requested release")
    require(health.get("database_connected") is True, "SHY database is disconnected")
    model_ready = (health.get("ollama_connected") is True and health.get("local_model_available") is True)
    if require_model:
        require(model_ready, "Ollama or the configured local model is unavailable")
    manifest = request_json(base_url, "/platform/capabilities")
    require(manifest.get("version") == expected_version, "Platform version mismatch")
    platform = manifest.get("platform", {})
    require(platform.get("sequence_complete") is True, "Milestone sequence is incomplete")
    require(platform.get("required_disabled_invariants_hold") is True, "Protected platform invariants failed")
    catalog = request_json(base_url, "/intelligence/capabilities")
    examples = json.loads(Path(examples_path).read_text(encoding="utf-8"))
    require(isinstance(examples, list) and len(examples) == 50, "Expected exactly 50 release examples")
    names = {item["capability"] for item in examples}
    require(len(names) == 50 and catalog.get("capability_count") == 50, "Capability catalog count mismatch")
    require({item["capability_id"] for item in catalog.get("capabilities", [])} == names,
            "Capability catalog does not match the release examples")
    require(catalog.get("external_execution") is False, "Utility external execution must be disabled")
    for item in examples:
        result = request_json(base_url, "/intelligence/evaluate", item)
        require(result.get("boundary") == "EVALUATED", f"{item['capability']}: evaluation failed")
        require(result.get("capability") == item["capability"] and result.get("side_effect_performed") is False,
                f"{item['capability']}: result identity or side-effect contract failed")
    batch = request_json(base_url, "/intelligence/batch", {"requests": examples[:10]})
    require(batch.get("all_evaluated") is True and len(batch.get("results", [])) == 10
            and batch.get("side_effect_performed") is False, "Batch evaluation contract failed")
    request_json(base_url, "/intelligence/evaluate", {"capability": "shell", "payload": {}}, 404)
    request_json(base_url, "/intelligence/evaluate", {"capability": "descriptive_stats", "payload": {"values": "invalid"}}, 422)
    request_json(base_url, "/intelligence/evaluate", {"capability": "descriptive_stats", "payload": {"text": "x" * (256 * 1024)}}, 413)
    return {"release_verified": True, "version": expected_version, "utility_examples_passed": 50,
            "database_connected": True, "local_model_available": model_ready,
            "model_inference_tested": False, "chat_generated": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--expected-version", default="0.105.6")
    parser.add_argument("--wait-seconds", type=float, default=60)
    parser.add_argument("--require-model", action="store_true", help="Also require Ollama and configured model availability; does not test inference")
    parser.add_argument("--examples", type=Path, default=Path(__file__).resolve().parents[1] / "docs/examples/intelligence-v100.json")
    args = parser.parse_args()
    try:
        require(0 <= args.wait_seconds <= 300, "Readiness wait must be between 0 and 300 seconds")
        result = verify(args.url, args.examples, args.expected_version, args.wait_seconds, args.require_model)
    except (VerificationError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        # Do not dump HTTP responses, environment values, database URLs, or traceback secrets.
        message = str(exc) if isinstance(exc, VerificationError) else "Unable to read or validate release evidence"
        print(json.dumps({"release_verified": False, "error": message}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
