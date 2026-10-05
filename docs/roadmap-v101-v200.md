# SHY v0.101–v0.200 implementation roadmap

This is the user-approved feature scope, not a claim that every milestone has
shipped. The current implementation is v0.105.0. A future number must not be added
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
speech quality, Windows execution, wake-word behavior, or GPU speech latency has
been measured by CI. Automated voice tests use fixtures, not acoustic recordings.

| Version | Feature | Status |
| --- | --- | --- |
| v0.101 | Push-to-talk, transcription, spoken replies | Implemented: browser-dependent; transcript review before Send |
| v0.102 | Stop speaking and interrupt voice playback | Implemented: client audio cancellation; server chat is not cancelled |
| v0.103 | Silence handling and recording limit | Implemented: browser speech-end events and 30-second limit; no custom VAD model |
| v0.104 | Microphone selection and audio diagnostics | Implemented: selected microphone, PCM WAV capture, level meter; configured local engine required |
| v0.105 | Voice, speed, and volume controls | Implemented: installed voice availability varies |
| v0.106 | English, French, Haitian Creole speech evaluation | Blocked: representative recordings and target-hardware quality measurements required |
| v0.107 | Language selection and automatic detection | Implemented early in v0.105: manual selection and local-engine auto detection; language quality unmeasured |
| v0.108 | Optional Hey SHY wake phrase | Planned |
| v0.109 | Hands-free conversation mode | Planned |
| v0.110 | Voice reliability, latency, privacy benchmarks | Planned: target microphone and hardware required |
| v0.111 | Conversation search | Implemented early in v0.103: browser history titles and messages |
| v0.112 | Editable conversation titles | Implemented early in v0.103: browser-local titles |
| v0.113 | Conversation summaries | Planned |
| v0.114 | Explicit remember-this requests | Planned: reconcile with existing durable-memory approval path |
| v0.115 | Review, correct, delete saved memories | Planned |
| v0.116 | Personal preferences with consent | Planned |
| v0.117 | Separate memory for each project | Planned |
| v0.118 | Memory conflict correction | Planned |
| v0.119 | Long-conversation context management | Planned |
| v0.120 | Memory accuracy and isolation benchmarks | Planned |
| v0.121 | Upload and read text files | Planned |
| v0.122 | PDF text extraction | Planned |
| v0.123 | Word document reading | Planned |
| v0.124 | Spreadsheet and CSV reading | Planned |
| v0.125 | Local document indexing | Planned |
| v0.126 | Search selected documents | Planned |
| v0.127 | Document-grounded answers with citations | Planned |
| v0.128 | Compare documents and changes | Planned |
| v0.129 | Refresh and remove indexed documents | Planned |
| v0.130 | Document-answer accuracy benchmarks | Planned |
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
| v0.141 | Connect evidence pipeline to chat | Planned |
| v0.142 | Approved web search integration | Planned: qualify existing research provider and credentials |
| v0.143 | Retrieve and cite public pages | Planned |
| v0.144 | Check source dates and freshness | Planned |
| v0.145 | Compare claims across sources | Planned |
| v0.146 | Clarify missing evidence | Planned |
| v0.147 | Show assumptions and concise explanations | Planned |
| v0.148 | Calculator-backed numerical answers | Planned |
| v0.149 | Compare options against user criteria | Planned |
| v0.150 | Research and reasoning benchmarks | Planned |
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

v0.106 requires genuine representative recordings and quality measurements for
English, French, and Haitian Creole. The v0.105 speech adapter supports selected
microphone streams when a local Whisper server is configured. Configuration is
not proof of availability or accuracy. A single English acoustic smoke case is
not a multilingual benchmark, a microphone test, or GPU performance evidence.
See [local speech setup](local-voice-v105.md) for the executable integration path.

## Release evidence

The current release gate runs Python contracts, web tests, lint, production build,
production dependency audit, and Docker runtime HTTP verification. The latter
checks the existing 50 supplied-data utilities. It does not validate acoustic
recognition or GPU inference. See [voice usage and boundaries](voice-v103.md).
