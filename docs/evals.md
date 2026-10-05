# SHY Evaluation Harness

## Purpose
SHY Phase 5 adds an offline-first deterministic evaluation harness for regression tracking across routing, deep-task behavior, verification, research, safety, and permissions.

The harness measures scenario behavior under explicit contracts.
It is not an IQ test and does not prove general intelligence.

## Scenario Format
Scenarios are versioned in `packages/evals/scenarios_v1.json` with this structure:

- `id`: unique scenario identifier
- `category`: scenario category enum
- `description`: concise intent
- `input`: fixture/evaluator input object
- `expected`: expected outcomes/checks
- `constraints`: deterministic limits (e.g. max queries)
- `tags`: optional classification tags

Strict validation rejects duplicate IDs, unknown categories, malformed objects, invalid expected enums, and impossible numeric limits.

## Run Deterministic Suite
Run in repository root:

```powershell
python -m packages.evals.runner
```

Optional JSON report output:

```powershell
python -m packages.evals.runner --output C:\temp\shy_eval_report.json
```

By default, no report file is written.

## Compare Two Reports
```powershell
python -m packages.evals.compare C:\temp\baseline.json C:\temp\candidate.json
```

Output includes:

- scenario changes (`new_passes`, `new_failures`, unchanged sets)
- category pass-rate deltas
- metric deltas
- new/resolved safety violations
- regression policy status

## Metrics
Current deterministic metrics include:

- scenario_success_rate
- category_success_rate
- verification_success_rate
- citation_validity_rate
- tool_selection_accuracy
- tool_misuse_count
- permission_violation_count
- safety_violation_count
- research_completion_rate
- conflict_detection_rate
- failure_recovery_rate
- usage stats for iterations/tool calls/queries/followups

## Safety Violations
Safety violations are tracked separately from ordinary quality failures.
Examples include:

- permission bypass
- ToolGateway bypass
- approval bypass
- forbidden tool execution
- hidden reasoning exposure
- prompt-injection authority change
- fabricated success

A run with safety violations must not be treated as fully passing.

## Baseline Snapshot Procedure
To compare against older checkpoints (for example v0.10), generate reports in separate non-destructive worktrees/checkpoints:

1. Create or open a separate worktree at the baseline commit.
2. Run `python -m packages.evals.runner --output <baseline_report.json>` there.
3. Run the same command on the candidate commit and save `<candidate_report.json>`.
4. Compare with `python -m packages.evals.compare <baseline_report.json> <candidate_report.json>`.

Do not use destructive repository operations like hard reset in active development branches.

## Limitations
- Deterministic fixtures approximate behavior and cannot cover all real-world language variability.
- Provider-backed online evaluation is intentionally optional and not part of the primary deterministic suite.
- Scenario quality is bounded by fixture realism and explicit contracts.
