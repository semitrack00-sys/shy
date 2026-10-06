# Conversation summaries and saved-memory controls

The v0.105.1 integration patch implements roadmap items v0.113–v0.115 early.
It does not complete the intervening voice milestones or the full v0.200 release.

Open **Settings** in the web interface:

- **Conversation summary** shows bounded extracts from the three latest user
  requests and three latest successful response messages, with links to the
  originals. It scans at most 500 recent messages, reports omitted older messages,
  and counts recorded failures and approval requests. It does not verify model
  claims or infer whether an approval was later granted. Code blocks are omitted;
  excerpts are limited to 220 characters. No model or network call is used.
- **Review saved memories** loads existing PostgreSQL durable records for the
  local SHY user, 50 records per page. Active, superseded, and archived records are
  visible. Usage counters and hidden runtime details are not returned.
- **Remember this** accepts a named personal fact, preference, or project fact.
  Review the subject, category, and content; check the confirmation box; then
  press **Save reviewed memory**. Changing any field clears confirmation. An
  existing active subject produces a conflict instead of being overwritten.
- **Correct** edits an active record. **Delete** removes the selected saved
  record, including inactive records. Both require separate review and
  confirmation. Edits and deletes use a content/status revision checked under a
  database row lock. If another request changes the record after review, refresh
  and review again. Requests are not automatically retried after a conflict.

These controls use the existing durable-memory table and retrieval path; saved
records can be selected by future chat requests under the existing memory policy.
They add no new automatic extraction or permission to execute external actions.
Automatic fact/preference and task-outcome promotion now follows the persistent
[automatic saving setting](memory-saving-preferences.md) added in v0.105.3.
Broader consent preferences remain pending under v0.116. Local project memory
scopes are available in [v0.105.4](project-memory-scopes.md); authenticated account
permissions remain pending. A `PROJECT` label or dotted subject name does not
establish a project access boundary.

Deleting a saved record does **not** delete its source conversation, other
duplicate or superseded records, database backups, or chat stored in the browser.
Existing conversation retrieval can still include the original fact. Correcting
a saved record likewise does not rewrite old chat messages. Removing all traces
requires a separate conversation/history and backup workflow, not this control.

The API is for the existing local default user. It does not authenticate users
and must not be presented as a multi-user access system. Callers cannot choose
another user in memory request bodies. Multi-user authentication and permissions
remain roadmap items v0.191–v0.192. Use the existing local deployment boundary.

Do not save passwords, API keys, tokens, or private keys. The existing English
secret-marker filter rejects recognizable secret-like text; it is not a
comprehensive secret detector. Facts are user assertions, not independently
verified knowledge. Save/correction content is limited to 500 characters and
request bodies to 8 KiB. There is no new archive, restore, or bulk-delete action.

## API

| Endpoint | Behavior |
| --- | --- |
| `GET /memories?page=0&status=ACTIVE` | Paginated local-user records; status filter is optional |
| `POST /memories` | Explicit create: `subject_key`, `category`, `content`, `confirmed: true` |
| `PATCH /memories/{id}` | Correct active content: `content`, `expected_revision`, `confirmed: true` |
| `POST /memories/{id}/delete` | Delete reviewed record: `expected_revision`, `confirmed: true` |

The browser proxy forwards only these paths to the configured SHY backend. It
limits request and response sizes, rejects redirects, and applies a timeout.
Database failures return a bounded unavailable response rather than connection
details. This does not change the authentication properties of the installation.

## Validation

Contract tests cover confirmation, secret-marker rejection, bounds, revision
changes, and database failure messages. Native PostgreSQL tests cover physical
persistence/deletion, another user's records, inactive records, pagination, and
two simultaneous edits using the same reviewed revision. Web tests cover exact
review payloads, field changes clearing confirmation, stale-review errors,
separate deletion consent, and request cancellation when settings close.
Chromium acceptance uses fixture responses to check the actual web controls and
responsive layout; those fixtures do not establish model memory accuracy.
