# Proposed memory preview and local data checks

v0.105.14 adds a read-only `POST /memories/preview?project_id=...` endpoint and a **Check existing memory subject** button in the saved-memory form. It compares the proposed category and content with active records for the exact subject in the selected local project. The preview returns `new_subject`, `same_saved_value` or `review_required`, existing public records with revision tokens, and explicit `saved: false` / `semantic_conflict_verified: false` flags. It does not promote, overwrite, archive or delete memories.

A single differing record in the same category can be opened as a correction with the proposed text preserved. The user must separately review that correction; the existing revision check rejects stale writes. Category differences and multiple active records require individual review. Preview lists at most two records and indicates more. Editing the proposed subject, category or content clears the preview and prior confirmation. Duplicate creation still fails even if a preview is stale or omitted. Matching subject labels do not prove that facts refer to the same context, and no semantic contradiction model runs.

The frontend proxy permits the preview path with the same streamed 8 KiB request guard and selected project query. The installation still has local project scopes rather than authenticated accounts.

## Fixed data benchmark

Run `python scripts/evaluate_local_data.py --report .validation/local-data.json` against a disposable PostgreSQL database. Without `DATABASE_URL` the command fails explicitly, instead of producing a passing skipped report. It creates uniquely named temporary projects and removes only their generated rows afterward.

The 62 per-case checks use three supplied memory records and four supplied documents (English, French, Haitian Creole and CSV). They check exact persistence, new/equal/different memory previews, preview without mutation, project separation, confirmed correction, stale write rejection, literal keyword matches, unchanged excerpts, stored revision provenance, missing keyword results and cross-project denial. The JSON report contains a fixture SHA-256 and individual results, and CI publishes it with release validation.

These small supplied examples are deterministic regression checks, not a representative multilingual corpus. They do not qualify broad memory retrieval accuracy, generated document answers, semantic understanding or account authentication. Roadmap v0.118, v0.120 and v0.130 remain partial; v0.150 is also unqualified.
