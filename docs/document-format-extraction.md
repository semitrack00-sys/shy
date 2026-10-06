# Bounded PDF, Word and spreadsheet text extraction

Patch v0.105.6 adds selected PDF/DOCX/XLSX reading to the local document controls,
implementing bounded roadmap v0.122/v0.123/v0.124. Choose a file in Settings,
confirm **Allow local text extraction of this selected file**, then press
**Extract selected document text**. The backend returns text without inserting
any document record. Review that text and separately confirm **Save reviewed
document** to index it. Changing the file clears both confirmations.

Only the selected binary is sent to the configured local SHY backend. Original
binary files are not written to disk or stored in the database. Extracted text
is returned with an original-file SHA-256 marker and format provenance; if saved,
that derived text enters the existing project index. Extraction does not train
models, execute document actions/formulas, run macros, fetch external links, or
read caller-chosen server paths. Files on your device remain untouched.

## Supported content

- **PDF:** text objects from 1–25 pages, with page markers. Encrypted PDFs and
  files with no extractable text are rejected. Image-only scans need separate
  OCR support, which this feature does not provide. Fonts, reading order, tables
  and layout can affect extraction; page markers do not prove extraction accuracy.
- **DOCX:** main-document paragraph text, including visible text in body tables,
  preserving accents, tabs and line breaks. Main XML must be UTF-8. Headers,
  footers, images, styling, embedded objects and legacy `.doc` are unsupported.
- **XLSX:** up to ten visible worksheets and 1,000 total row records, at most
  50 columns, with sheet names and original cell references. Hidden sheets are
  omitted. Shared and inline strings, literal numeric/date/error/boolean values
  and formula source/cached values are read as text. Formulas are explicitly
  labeled **not evaluated**; cached values may be stale and are not verified.
  Number/date formats are not interpreted. Macros, legacy `.xls`, external data
  refresh, calculations and chart/image extraction are unsupported.

Unsupported or over-limit documents fail instead of silently indexing a partial
result. Successfully extracted text can still omit layout-specific information;
review it against the original before relying on it. These checks do not complete
the broader document-answer accuracy milestone v0.130.

## Resource and execution bounds

The API accepts strictly validated base64 files up to **1 MiB**, with an exact
boolean confirmation and a **2 MiB** streamed JSON body cap. Only two workers can
run per backend process; additional requests receive HTTP 429. The fixed command
is the current Python executable in isolated mode and the bundled parser script,
with no shell, arbitrary command arguments, or caller-selected file path.
The worker receives a reduced environment without database/API credentials.

Workers have a **256 MiB** memory limit (Unix address space, Windows committed
process memory), **5 seconds** CPU time and **10 seconds** communication/extraction
wall timeout. The parent kills timed-out workers. Windows Job Object assignment
must succeed before any document bytes are sent; Unix resource limits are applied
before input parsing. Limits unavailable on a platform cause failure, not an
uncapped fallback. Resource limits do not measure speed on the user's hardware.

ZIP packages are bounded to 200 entries, 8 MiB total expanded size and 2 MiB per
entry, with at most 100:1 expansion. Traversal/duplicate/encrypted/symlink entries,
embedded binary/macro files and XML DTD/entities are rejected. XML is read from
memory without extracting an archive into the filesystem. PDF decoded page
streams are capped at 4 MiB inside the worker. Parsed output is at most 100,000
Unicode characters and 256 KiB UTF-8. DOCX paragraphs and XLSX cell/string limits
are checked before returning data. Existing text/index upload confirmation and
project controls still apply.

`POST /documents/extract?project_id=<optional-project>` accepts `kind` (`pdf`,
`docx`, `xlsx`), base64 `data`, and `confirmed: true`. It returns derived `content`,
source hash, format diagnostics, resource-limit metadata, and
`binary_stored: false`. The operation does not access document storage. Malformed,
encrypted, empty or oversized inputs return bounded HTTP 422 errors; unavailable
workers return HTTP 503 without internal details. The browser proxy uses the
fixed backend, no redirects, bounded responses and a 15-second timeout.

## Validation

The full Linux release gate runs real PDF, DOCX and XLSX extraction fixtures,
including accented text, source hashes, encrypted/empty/too-many-page rejection,
XML entities, invalid archive paths, macro/binary/expansion rejection, hidden
worksheet omission, formula non-execution, cell limits, strict consent and
resource-slot/timeout behavior. A dedicated native Windows CI job runs the same
real workers with Job Object limits. Browser acceptance uses fixtures to test
separate extraction and text-save consent. These checks do not establish OCR,
complete document fidelity, or performance on the user's Windows PC.
