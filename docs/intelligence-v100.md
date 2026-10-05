# SHY v0.51–v0.100: bounded intelligence utilities

These milestones extend the verified v0.50 code at `e8926917eafdf3af8298635400f43c57b85927d2`.
No roadmap beyond v0.50 existed in that checkout. This release defines 50 small,
individually tested utility contracts in five groups: retrieval, workflows, data,
security, and operational evidence. These numbers identify software milestones;
they do not measure intelligence, accuracy, or an increase in model capability.

## API

- `GET /intelligence/capabilities`: catalog of all 50 implemented handlers.
- `POST /intelligence/evaluate`: `{ "capability": "descriptive_stats", "payload": { "values": [1, 2, 3] } }`.
- `POST /intelligence/batch`: `{ "requests": [...] }`, at most 10 evaluations.
- `/docs` and `/openapi.json`: discover the request envelopes on the running SHY core.

A successful response has boundary `EVALUATED`, the introduced version, a SHA-256
fingerprint of the supplied input, and the result payload. This means computation
completed, including computations that conclude the data is unsafe or insufficient.
Unknown capabilities return HTTP 404. Invalid domain input returns HTTP 422.
Oversized bodies return HTTP 413 before JSON parsing. A batch keeps each result's
failure boundary instead of treating partial success as complete success.

Inputs and outputs are limited to 256 KiB, 500 entries per collection, 16,000
characters per string, and 12 levels of payload nesting. No handler opens files,
fetches URLs, runs shell commands, dispatches jobs, makes payments, modifies
permissions, persists memory, or deploys anything. Output bounds are checked too.

The scope field filters **supplied** passages. It is not authentication and does
not access stored users, conversations, or knowledge. Caller-supplied `verified`,
`passed`, checksums, and approval fields are not independently authenticated.
Checksums establish equality/integrity against a supplied digest, not authenticity.
URL/path policies are previews: DNS, redirects, and symlinks still require gateway
checks before a future operation. Injection detection and redaction are heuristic,
not exhaustive security certification. Citation checking verifies literal quotes;
it does not establish factual truth or semantic entailment. BM25 relevance and
lexical coverage do not establish answer accuracy.

The v0.100 evidence pipeline ranks in-scope passages, quarantines stale/future or
instruction-risk sources, redacts common secrets and PII, packs complete passages
within a citation-aware character budget, and evaluates lexical answerability,
structured conflicts, and supplied quotes. It emits `EVIDENCE_AVAILABLE`,
`DATA_REQUIRED`, or `CONFLICT`. It **does not generate an answer**, alter `/chat`,
or connect a new model provider. It is available to API callers; it is not a new
chat-screen control. All existing chat, memory, routing, and approval paths remain.

## Milestone catalog

Each capability has a runnable input in [the complete examples](examples/intelligence-v100.json)
and a targeted test in `tests/test_intelligence_v051_v060.py` through
`tests/test_intelligence_v091_v100.py`. Every example is also exercised through HTTP.

| Milestone | Capability |
| --- | --- |
| v0.51 | `chunk_text` |
| v0.52 | `rank_passages` |
| v0.53 | `fuse_rankings` |
| v0.54 | `pack_context` |
| v0.55 | `validate_citations` |
| v0.56 | `detect_conflicts` |
| v0.57 | `source_freshness` |
| v0.58 | `consolidate_memory` |
| v0.59 | `redact_text` |
| v0.60 | `answerability` |
| v0.61 | `schedule_tasks` |
| v0.62 | `critical_path` |
| v0.63 | `verify_checkpoint` |
| v0.64 | `retry_policy` |
| v0.65 | `idempotency_fingerprint` |
| v0.66 | `allocate_budget` |
| v0.67 | `cancellation_plan` |
| v0.68 | `approval_binding` |
| v0.69 | `recovery_plan` |
| v0.70 | `dry_run` |
| v0.71 | `profile_schema` |
| v0.72 | `descriptive_stats` |
| v0.73 | `detect_outliers` |
| v0.74 | `missing_report` |
| v0.75 | `deduplicate_rows` |
| v0.76 | `join_rows` |
| v0.77 | `aggregate_rows` |
| v0.78 | `transform_rows` |
| v0.79 | `compare_snapshots` |
| v0.80 | `data_quality` |
| v0.81 | `injection_scan` |
| v0.82 | `url_policy` |
| v0.83 | `path_policy` |
| v0.84 | `permission_diff` |
| v0.85 | `tool_contract` |
| v0.86 | `audit_chain` |
| v0.87 | `config_check` |
| v0.88 | `dependency_lock` |
| v0.89 | `backup_verify` |
| v0.90 | `provenance_trace` |
| v0.91 | `health_summary` |
| v0.92 | `slo_report` |
| v0.93 | `latency_report` |
| v0.94 | `cluster_errors` |
| v0.95 | `capacity_estimate` |
| v0.96 | `regression_report` |
| v0.97 | `evaluation_scorecard` |
| v0.98 | `release_gate` |
| v0.99 | `compatibility_report` |
| v0.100 | `evidence_pipeline` |

## Validation

Use a disposable PostgreSQL database, then run:

```sh
python -m pip install -r services/core/requirements.txt
python -m compileall -q services packages tests scripts
python scripts/validate_release.py --report .validation/v100-python.json
cd apps/web
npm ci
npm test
npm run lint
npm run build
npm audit --omit=dev --audit-level=high
```

The runner includes the current milestone, registry, endpoint, full SHY core
startup/integration, and protected historical unit/contract regressions. It records
excluded historical external-HTTP/provider scripts separately. Those scripts often
require an exact older runtime version and are not valid evidence against v0.100.
The new GitHub release gate uses PostgreSQL 16 and Python 3.13, and uploads its report.
Local database-backed validation uses disposable PGlite (PostgreSQL compiled to
WebAssembly) because native PostgreSQL cannot be installed in this workspace.
GitHub CI supplies independent native PostgreSQL coverage. Controlled and supplied
data tests do not measure Qwen answer quality, GPU latency, audio, or image inference.

## Repository and local rollout

The v0.100 release was integrated through PR #40 into
`codex/shy-v0.50-integrated-platform`. The promotion to `main` includes the full
v0.11–v0.100 history. Use `main` after the promotion PR is merged and its release
checks pass. The existing default branch, `codex/shy-v0.9-web-research`, is
historical and does not contain this release; select `main` explicitly.

On the SHY computer, first inspect `git status` and preserve any uncommitted work.
Fetch `main` and review the release commit before replacing the local runtime. The Dockerfile copies the
new modules using its existing core/agent-runtime layout. A rebuild can use
`docker build -t shy-core:0.100 .`; the existing database and Ollama environment
settings remain required. Do not replace or delete an existing local container
until its configuration and data volumes have been checked. This repository release
does not install itself on `C:\SHY`, restart the user's container, or change hosting.
