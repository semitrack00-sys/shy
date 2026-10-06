# Selected local document controls

Integration patch v0.105.5 implements bounded text/Markdown upload and reading,
project-scoped indexing, selected keyword search, and reviewed index refresh and
removal (roadmap v0.121/v0.125/v0.126/v0.129). CSV support is part of v0.124;
Excel remains pending. Extractive evidence citations and literal comparison are
partial v0.127/v0.128, not semantic answer generation or document understanding.
PDF and Word are not parsed by this release.

Open Settings → **Review local documents**. Select a `.txt`, `.md`, or `.csv`
file, review its name/type/character count and preview, confirm that exact change,
and press **Save reviewed document**. A changed file clears confirmation.
Only the selected file is read; no directory scanning, arbitrary file paths,
network fetch, automatic memory promotion or model training is performed.
The original file on your device is untouched.

Choose up to five indexed documents and enter **Document search keywords**.
Results show exact source excerpts, document names, line ranges and chunk numbers.
Search uses PostgreSQL's `simple` full-text dictionary with up to 20 Unicode
word/number terms, OR matching, and ranked results. It is lexical, not semantic:
missing evidence is reported instead of synthesizing unsupported statements.
Accents are retained; stemming, accent-insensitive matching and exhaustive recall
are not promised. Individual excerpts are at most 1,000 Unicode characters and
are exact contiguous source slices, so a very long word may cross a chunk edge.
Text statements are not independently verified facts.

**Read** shows stored text. **Review refresh** replaces the selected record with
a newly selected file after confirmation, rebuilds its chunks in the same
transaction, and changes its revision. **Review delete** requires separate
confirmation and removes both document text and indexed chunks. Neither action
removes the original device file, exported excerpts, chats or database backups.
Stale reviews return HTTP 409; callers must reload and review again. Refresh
revisions include a nonce, so restoring old text does not reactivate old reviews.

Choose exactly two files for **Compare two selected documents**. Comparison uses
literal unique line sets, retaining original line numbers in bounded difference
excerpts. It is not semantic comparison, an aligned patch, verification of claims,
or proof that two differently formatted documents agree.

## Bounds and storage

- UTF-8 content: at most 100,000 Unicode characters and 256 KiB; nonempty, no NUL.
  The browser's UTF-16 length check can be stricter for supplementary characters.
- JSON request body: 512 KiB; browser proxy response: 1 MiB; no redirects and a
  15-second proxy timeout. Requests have strict schemas and literal confirmation.
- 30 documents per local project; quota checked under a transaction advisory lock.
- At most 250 indexed chunks per document, each at most 1,000 characters.
- CSV: at most 1,000 rows, 50 columns and 4,000 characters per cell. Values that
  resemble formulas are counted in diagnostics and preserved as text. No formula
  evaluation, macros, external links or inferred numeric calculations occur.
- Search: 1–5 explicitly selected documents, query at most 500 characters,
  response at most 10 excerpts (the UI requests five).
- Comparison: two documents, at most 30 difference excerpts per side, each line
  preview at most 500 characters; counts refer to unique literal lines.

PostgreSQL stores original text and its project-scoped index. These controls use
the same local project identity as chat/memory, but do not authenticate callers.
Anyone with access to this local backend can select a project by name. Do not
upload passwords, private keys or API tokens. Encryption and multi-user access
permissions remain separate unfinished milestones.

## API

Every endpoint accepts optional `project_id` as a query parameter.

| Endpoint | Behavior |
| --- | --- |
| `GET /documents` | At most 30 metadata records for the selected project |
| `POST /documents` | Confirmed `name`, `kind: text/csv`, and UTF-8 `content` |
| `GET /documents/{id}` | Stored text plus metadata/revision, owner checked |
| `PATCH /documents/{id}` | Confirmed replacement fields plus `expected_revision`; atomic reindex |
| `POST /documents/{id}/delete` | Confirmed `expected_revision`; cascading chunk deletion |
| `POST /documents/search` | `query`, explicit `document_ids`, optional `limit` |
| `POST /documents/answer` | Same search schema; exact excerpts with document/chunk/revision evidence, no generated claims |
| `POST /documents/compare` | Exactly two explicit `document_ids`; literal line comparison |

Contract tests cover parsers, exact Unicode source reconstruction, formula
non-execution, strict confirmation, bounds and failure messages. Native
PostgreSQL tests exercise persistence/full-text search, source revisions,
project isolation, index replacement/removal, stale/concurrent reviews,
A→B→A revision protection and quota. Web and fixture-based Chromium tests cover
user review, project query scope, selected sources, refresh/deletion and layout.
These regressions do not complete the broader answer-accuracy benchmark v0.130.
