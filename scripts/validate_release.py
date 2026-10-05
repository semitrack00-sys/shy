"""Run current contracts and protected regressions; requires a disposable PostgreSQL DB.

Historical external-HTTP tests require their original versioned runtimes and model
providers and are deliberately reported as excluded, never counted as passing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="/tmp/shy-v100-validation.json")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    environment = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""), "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
    results, excluded = [], []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if "live" in path.name or path.name == "test_advanced_memory_api_integration.py":
            excluded.append({"script": path.name, "reason": "requires_original_versioned_runtime_or_external_provider"})
            continue
        start = time.monotonic()
        try:
            result = subprocess.run([sys.executable, str(path)], cwd=ROOT, env=environment, capture_output=True, text=True, timeout=args.timeout)
            status = "passed" if result.returncode == 0 else "failed"
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            status, output = "failed", "script_timeout"
        results.append({"script": path.name, "status": status, "seconds": round(time.monotonic() - start, 3), "output_tail": output[-5000:]})
        print(f"{status.upper()}: {path.name}", flush=True)
    tracked = subprocess.check_output(["git", "ls-files", "services", "tests", "scripts", "docs/examples"], cwd=ROOT, text=True).splitlines()
    # Include untracked additions while a candidate is being developed.
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "services", "tests", "scripts", "docs/examples"], cwd=ROOT, text=True).splitlines()
    fingerprint = hashlib.sha256()
    for relative in sorted(set(tracked + untracked)):
        path = ROOT / relative
        if path.is_file():
            fingerprint.update(relative.encode() + b"\0" + path.read_bytes() + b"\0")
    failed = [x["script"] for x in results if x["status"] != "passed"]
    report = {"version": "0.100.0", "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "source_sha256": fingerprint.hexdigest(), "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()), "python": sys.version, "script_count": len(results), "passed_count": len(results) - len(failed), "failed_scripts": failed, "excluded": excluded, "results": results, "real_model_quality_measured": False}
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Release validation: {report['passed_count']}/{len(results)} scripts passed; {len(excluded)} external/versioned scripts excluded.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
