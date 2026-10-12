# SHY v0.101–v0.200 implementation roadmap

This is the user-approved feature scope, not a claim that every milestone has
shipped. The current implementation is v0.105.16. A future number must not be added
to the runtime manifest merely because its plan exists. Version numbers identify
releases; model intelligence and hardware performance require separate measurements.

Status meanings: **Implemented** = code and automated tests exist, with the stated
runtime conditions; **Implemented early** = available ahead of its planned number but its planned
release number has not been issued; **Partial** = only some required behavior is
implemented; **Blocked** = the next sequential milestone needs a concrete missing
prerequisite; **Planned** = not implemented by this release.

Browser voice requires compatible APIs and permission. Local recognition depends
on browser language packs. Remote browser speech requires session-only opt-in.
The core has an optional bounded local Whisper HTTP adapter; no model is installed
in the core image. No real microphone, Haitian Creole
speech quality, execution on the user’s Windows machine, acoustic wake-word behavior, or GPU speech latency has
been measured by CI. Browser voice UI tests use fixtures. A separate acoustic
smoke test uses a real English recording with the local Whisper engine on CPU.

| Version | Feature | Status |
| --- | --- | --- |
| v0.101 | Push-to-talk, transcription, spoken replies | Implemented: browser-dependent; transcript review before Send |
| v0.102 | Stop speaking and interrupt voice playback | Implemented: client audio cancellation; server chat is not cancelled |
| v0.103 | Silence handling and recording limit | Implemented: browser speech-end events and 30-second limit; no custom VAD model |
| v0.104 | Microphone selection and audio diagnostics | Implemented: selected microphone, PCM WAV capture, level meter; configured local engine required |
| v0.105 | Voice, speed, and volume controls | Implemented: installed voice availability varies |
| v0.106 | English, French, Haitian Creole speech evaluation | Runner and offline corpus importer implemented; genuine multilingual recordings and measured results pending |
| v0.107 | Language selection and automatic detection | Implemented early in v0.105: manual selection and local-engine auto detection; language quality unmeasured |
| v0.108 | Optional Hey SHY wake phrase | Implemented early in v0.105.7: explicit bounded browser transcript-prefix session, not an acoustic wake model |
| v0.109 | Hands-free conversation mode | Implemented early in v0.105.7: separate automatic-send consent, response/playback pause, no voice tool approvals; browser support required |
| v0.110 | Voice reliability, latency, privacy benchmarks | Planned: target microphone and hardware required |
| v0.111 | Conversation search | Implemented early in v0.103: browser history titles and messages |
| v0.112 | Editable conversation titles | Implemented early in v0.103: browser-local titles |
| v0.113 | Conversation summaries | Implemented early in v0.105.1: bounded excerpts with links; no inferred facts or completion |
| v0.114 | Explicit remember-this requests | Implemented early in v0.105.1: reviewed facts saved in existing durable memory; automatic chat promotion unchanged |
| v0.115 | Review, correct, delete saved memories | Implemented early in v0.105.1: local-user pagination and revision-checked changes; original history remains |
| v0.116 | Personal preferences with consent | Partial early in v0.105.3: confirmed persistent automatic-memory pause/resume; legacy default enabled until reviewed; broader consent preferences pending |
| v0.117 | Separate memory for each project | Implemented early in v0.105.4: local project conversation, durable-memory and saving-preference scopes; not authenticated account isolation |
| v0.118 | Memory conflict correction | Partial early in v0.105.14: read-only exact-subject/value preview with revision-preserving, separately reviewed correction; semantic conflict detection remains pending |
| v0.119 | Long-conversation context management | Implemented early in v0.105.2: ordinary chat history uses hard excerpt budgets, including fallback; older context can be omitted |
| v0.120 | Memory accuracy and isolation benchmarks | Partial early in v0.105.14: fixed PostgreSQL persistence, exact correction, stale-write and project isolation checks; representative memory retrieval accuracy and account authentication remain unqualified |
| v0.121 | Upload and read text files | Implemented early in v0.105.5: confirmed UTF-8 text/Markdown uploads and bounded reading |
| v0.122 | PDF text extraction | Implemented early in v0.105.6: selected text-bearing PDFs, capped worker and page provenance; no OCR |
| v0.123 | Word document reading | Implemented early in v0.105.6: DOCX main-document text; legacy DOC and full layout unsupported |
| v0.124 | Spreadsheet and CSV reading | Implemented early in v0.105.6: bounded CSV and visible XLSX stored-cell text; formulas/macros never executed; legacy XLS unsupported |
| v0.125 | Local document indexing | Implemented early in v0.105.5: PostgreSQL project-scoped text index |
| v0.126 | Search selected documents | Implemented early in v0.105.5: explicit selection, local keyword search and source provenance |
| v0.127 | Document-grounded answers with citations | Partial early in v0.105.5: extractive source excerpts with document/chunk/revision citations; v0.105.15 brings explicitly selected excerpts into ordinary chat/history with literal rendering and no-model provenance; generated answers pending |
| v0.128 | Compare documents and changes | Partial early in v0.105.5: bounded literal line comparison; v0.105.16 adds ordered logical-line changes, repeated-line counts, bounded previews and a consistent revision snapshot; semantic comparison pending |
| v0.129 | Refresh and remove indexed documents | Implemented early in v0.105.5: reviewed revision refresh/delete; index updated atomically |
| v0.130 | Document-answer accuracy benchmarks | Partial early in v0.105.14: fixed English/French/Haitian Creole and CSV excerpt/provenance/isolation checks; generated answer accuracy and representative corpus qualification remain pending |
| v0.131 | Connect a local vision model | Planned: model download and hardware validation required |
| v0.132 | Image upload and questions | Planned |
| v0.133 | Printed-text extraction from images | Planned |
| v0.134 | Screenshot and interface understanding | Planned |
| v0.135 | Photographed receipts and invoices | Planned |
| v0.136 | Charts with uncertainty reporting | Planned |
| v0.137 | Compare multiple images | Planned |
| v0.138 | User-selected screen capture | Planned |
| v0.139 | Voice, images, text in one request | Planned |
| v0.140 | Visual accuracy and privacy benchmarks | Planned |
| v0.141 | Connect evidence pipeline to chat | Partial early in v0.105.11: ordinary research chat returns source cards and response provenance; broader live-provider and real-model qualification pending |
| v0.142 | Approved web search integration | Planned: qualify existing research provider and credentials |
| v0.143 | Retrieve and cite public pages | Partial early in v0.105.9: existing research synthesis enforces citation/source membership and prompt/source numbering; full-page retrieval and live provider qualification remain pending |
| v0.144 | Check source dates and freshness | Partial early in v0.105.10: provider date estimates, separate retrieval times, conservative English recency hints and dated citation gates; verified page dates and live-provider qualification pending |
| v0.145 | Compare claims across sources | Partial early in v0.105.11: matching atomic field/value snippets and existing workflow conflict flags produce cited clarification; general prose semantic comparison and quality qualification remain pending |
| v0.146 | Clarify missing evidence | Partial early in v0.105.10: missing qualifying date evidence returns clarification before generation; v0.105.11 also clarifies empty excerpts and possible disagreements; broader missing-claim evidence handling remains pending |
| v0.147 | Show assumptions and concise explanations | Partial early in v0.105.12: research answer context explains model invocation, checked source records, date-window assumptions and unresolved truth/subject limits; general reasoning explanations and quality benchmarks remain pending |
| v0.148 | Calculator-backed numerical answers | Implemented early in v0.105.8: bounded explicit decimal arithmetic through actual agent/chat paths, stored replies and project ownership; no inferred units or word-problem solver |
| v0.149 | Compare options against user criteria | Implemented early in v0.105.13 for explicitly supplied numeric criteria: weighted min/max ranking, ties, input table and project-scoped chat; natural-language criteria extraction and factual value gathering are not implemented |
| v0.150 | Research and reasoning benchmarks | Partial early in v0.105.13: 33 fixed offline reference cases with a hashed JSON report and CI gate (expanded to 38 in v0.105.16 for ordered document lines); live model quality, semantic claim support, representative questions and target hardware latency remain pending |
| v0.151 | Read approved local folders | Planned: target-machine filesystem access required |
| v0.152 | Preview file creation and edits | Planned |
| v0.153 | Approved edits with backups | Planned |
| v0.154 | Open approved applications | Planned: target-machine execution bridge required |
| v0.155 | Read approved browser sessions | Planned |
| v0.156 | Preview browser actions | Planned |
| v0.157 | Complete approved form fields | Planned |
| v0.158 | Approved multi-step computer tasks | Planned |
| v0.159 | Task cancellation, recovery, history | Planned |
| v0.160 | Computer-action safety benchmarks | Planned |
| v0.161 | Formatted letters and reports | Planned |
| v0.162 | Generate PDF documents | Planned |
| v0.163 | Invoices from supplied information | Planned |
| v0.164 | Spreadsheets with checked calculations | Planned |
| v0.165 | Presentations from outlines | Planned |
| v0.166 | Email drafts with recipient review | Planned |
| v0.167 | Approved email integration | Planned: account and OAuth connection required |
| v0.168 | Approved calendar integration | Planned: account and OAuth connection required |
| v0.169 | Business templates and terminology | Planned |
| v0.170 | Document and business-workflow benchmarks | Planned |
| v0.171 | Task progress across restarts | Planned |
| v0.172 | Local reminders | Planned |
| v0.173 | Scheduled tasks | Planned |
| v0.174 | Conditional checks on approved sources | Planned |
| v0.175 | Background task queue | Planned |
| v0.176 | Notifications and status dashboard | Planned |
| v0.177 | Retry limits and duplicate prevention | Planned |
| v0.178 | Expiring scheduled-action approvals | Planned |
| v0.179 | Automation pause, cancellation, recovery | Planned |
| v0.180 | Automation reliability benchmarks | Planned |
| v0.181 | CPU, RAM, GPU, model diagnostics | Planned: hardware access required |
| v0.182 | Measure chat and voice latency | Planned |
| v0.183 | Hardware-based model selection | Planned |
| v0.184 | Route to tested specialist models | Planned |
| v0.185 | Model loading and memory limits | Planned |
| v0.186 | Concurrent-request controls | Planned |
| v0.187 | Isolated caching of eligible results | Planned |
| v0.188 | Optional cloud fallback with consent | Planned: provider credentials required |
| v0.189 | Model comparison and regression dashboard | Planned |
| v0.190 | Publish measured quality and performance | Planned: genuine benchmark evidence required |
| v0.191 | User accounts and authentication | Planned |
| v0.192 | User permissions and isolation | Planned |
| v0.193 | Encrypt stored secrets | Planned |
| v0.194 | Backup and tested restoration | Planned |
| v0.195 | Windows installer and setup | Planned: Windows build and execution required |
| v0.196 | Verified updates and rollback | Planned |
| v0.197 | Responsive phone and tablet interface | Planned: existing responsive shell is a foundation |
| v0.198 | Accessibility and expanded UI languages | Planned |
| v0.199 | Security, recovery, acceptance testing | Planned |
| v0.200 | Integrated release with documented limits | Planned: prior release acceptance required |

## Next sequential prerequisite

The v0.105.1 patch implements memory controls ahead of their planned release
numbers. See [saved memory controls](saved-memory-controls.md) for usage,
confirmation, persistence, deletion scope, and the remaining authentication and
project-isolation limits. No v0.106–v0.115 release numbers are claimed complete.
The v0.105.2 patch enforces [ordinary chat history budgets](chat-context-limits.md).

v0.106 requires genuine representative recordings and quality measurements for
English, French, and Haitian Creole. The v0.105 speech adapter supports selected
microphone streams when a local Whisper server is configured. Configuration is
not proof of availability or accuracy. A single English acoustic smoke case is
not a multilingual benchmark, a microphone test, or GPU performance evidence.
See [local speech setup](local-voice-v105.md) for the executable integration path.
The [speech evaluation guide](speech-evaluation.md) includes an offline importer
for officially downloaded Common Voice test splits. Mozilla account access and
download consent are required for that source; SHY does not bypass them. Other
consented recordings with checked references can also use the evaluator.

## Release evidence

The current release gate runs Python contracts, web tests, lint, production build,
production dependency audit, and Docker runtime HTTP verification. The latter
checks the existing 50 supplied-data utilities. A separate local-speech job runs
a real English recording through the pinned Whisper engine on CPU. This checks
the acoustic integration, not multilingual quality or GPU inference. See
[voice usage and boundaries](voice-v103.md).

The v0.105.3 patch adds [automatic memory saving controls](memory-saving-preferences.md), including persistent pause/resume enforced across automatic fact and task-outcome promotions.

The v0.105.4 patch adds [local project memory scopes](project-memory-scopes.md) and fixes the default chat/control identity mismatch.

The v0.105.5 patch adds [selected local text/CSV document controls](local-documents.md). Parser/index/isolation regressions do not complete the broader document-answer accuracy milestone v0.130.

The v0.105.6 patch adds [bounded PDF/DOCX/XLSX text extraction](document-format-extraction.md), with a native Windows worker release check.


The v0.105.7 patch adds [bounded browser wake sessions](browser-wake-sessions.md). Genuine multilingual and target-hardware benchmarks remain pending.

The v0.105.8 patch hardens and connects the [bounded decimal calculator](calculator-chat.md) to both chat entry points.

The v0.105.9 patch enforces [research citation membership](research-citation-checks.md). It does not complete source truth, freshness or research accuracy benchmarks.

The v0.105.10 patch adds [provider date estimate checks](research-source-dates.md) and missing-current-evidence clarification. Verified publication dates, multilingual intent detection and research quality benchmarks remain pending.

The v0.105.11 patch adds [bounded disagreement clarification](research-disagreement-checks.md), source cards in ordinary research chat and accurate provenance for replies that did not invoke a model. This does not complete general semantic comparison or research quality benchmarks.

The v0.105.12 patch adds [research answer context](research-answer-context.md) and fixes source-card rendering for ordinary research chat. Counts, date windows and model-invocation details are bounded public check descriptions, not private model reasoning or independent claim verification.

The v0.105.13 patch adds [criteria comparisons and bounded reasoning checks](option-comparisons.md). These do not complete the speech, visual, live research or hardware qualification required across v0.106–v0.150.

The v0.105.14 patch adds [memory preview and local data checks](memory-preview.md), with a hashed per-case PostgreSQL report. Exact supplied-data checks are not representative language or generated-answer accuracy measurements.

The v0.105.15 patch adds [selected document chat](selected-document-chat.md). Only explicitly selected, owner-checked keyword excerpts are returned; broad semantic document answers remain unqualified.

The v0.105.16 patch adds [ordered document comparisons](ordered-document-comparison.md). Repeated and reordered logical lines are checked within explicit limits, with unchanged source semantics qualification.
