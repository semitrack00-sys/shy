# Ordered document comparisons

v0.105.16 extends `POST /documents/compare` with `ordered_comparison` while preserving the original unique-line fields. Two explicitly selected documents are checked against the local project and read in a single repeatable-read, read-only PostgreSQL transaction. Both source revision hashes appear in the web preview. Comparison does not alter documents or indexes.

The previous unique-line summary ignores order and occurrence counts. The new comparison retains repeated logical lines and returns insertion, deletion and replacement groups from deterministic sequence alignment. Reordering can appear as an insertion and deletion; it is not independently classified as a semantic move. A minimal edit script is not guaranteed, and the output is not an executable patch.

Limits are 100,000 characters and 1,000 logical lines per source. Logical lines use Python `splitlines()` without separators; line separator and final newline differences are excluded from line alignment. `text_identical` separately compares the complete stored strings. When limits are exceeded, ordered checks return unavailable with a specific reason, while the original unique-line summary remains available.

Aggregate counts cover the entire evaluated alignment. The preview shows at most 10 change groups, two sample lines per side and 150 characters per sample. Samples carry source line positions and explicit truncation flags; omitted line/group counts and the overall truncation flag prevent a partial preview from being presented as all source changes. The browser validates count conservation, ranges, operation types, constant limits and omission consistency, and renders source text literally. If an older runtime does not provide ordered checks, the UI says so.

Validation covers repeated-line deletion, reordering with identical unique-line sets, known insert/delete/replace ranges, ignored line endings, bounded worst-case repeated lines, omission counts, source text without execution, project isolation and a real concurrent refresh between the two database reads. Chromium fixtures check both revision labels, comparison without mutation and phone/desktop overflow. This advances partial roadmap v0.128; semantic document comparison and broader accuracy qualification remain unfinished.

The fixed reasoning benchmark now contains 38 cases, adding five reference cases for duplicate lines, reordering, line endings, replacement and ordered-line limits. These remain synthetic deterministic checks, not representative semantic accuracy measurements.
