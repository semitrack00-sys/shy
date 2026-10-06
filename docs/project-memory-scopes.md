# Local project memory scopes

Patch v0.105.4 implements the local project memory part of roadmap v0.117.
In Settings, enter a **New project ID** and press **Start project chat**. IDs are
1–64 lowercase ASCII letters/digits, dots, underscores or dashes, starting with a
letter or digit. Leave the field blank to start a default chat. Existing chats
keep their original scope; new chats inherit the active project unless the
project form explicitly selects another scope. Project IDs persist with browser
conversation records. This is organization within one local installation, not
an authenticated account boundary.

The chat API accepts optional `project_id`. Project chats use separate database
conversation owners, message history and durable-memory users derived from the
fixed local user and project ID. Cross-conversation retrieval stays inside that
scope. An existing conversation ID from another scope returns HTTP 404 rather
than being reused. A `PROJECT` category or dotted subject alone is insufficient:
all memory categories in a project follow the selected scope.

Memory list/create/correct/delete and automatic-saving preferences accept the
same `project_id` query parameter. Preference revisions and locks are independent
per scope. Editing/deleting another project's memory ID returns 404. Changing
projects unmounts the old review controls and clears prior confirmation; no
reviewed fields or revisions are reused across projects. The browser proxy only
forwards the validated scope query to the fixed backend. Automatic task-outcome
promotions use the same effective project memory identity. Project requests also
set the existing knowledge/workflow workspace scope to `project.<id>`.

Default chat had historically used the anonymous workflow-derived ID for durable
promotion, while conversations and manual memory controls used the fixed local
user. This patch makes unscoped local chat use the same fixed identity as its
controls. Startup reassigns legacy anonymous-default durable records when their
source conversation belongs to the default local user, or when they have no
source conversation. Records tied to other conversation owners are untouched.
Existing saved-memory IDs/content are retained. This fixes default pause/resume
and makes those old local facts reviewable through the memory manager.

Requests cannot combine `project_id` with legacy `user_id`, `workspace_id`, or
`business_id` fields. Legacy explicitly scoped API clients still use their own
existing identity rules and are not managed by this local-project interface.
The default user and each new project preserve automatic-saving enabled until
reviewed. Pausing one project does not pause another.

This API does not authenticate project selection. A caller with access to the
local backend can select another project by name; do not describe these scopes
as permissions or tenant isolation. Shared local users can see browser history.
Project scopes do not add encryption, erase chat/backups, isolate filesystem
access, or complete every task/knowledge subsystem security benchmark. Those
remain separate roadmap requirements.

Validation runs the real chat handler with deterministic generation only:
PostgreSQL-backed promotion, retrieval, history and API controls are exercised
without replacing their persistence logic. Tests cover default pause enforcement,
project history/memory separation, cross-scope correction/deletion and conversation
reuse rejection, separate preferences, invalid/mixed scope rejection and legacy
migration. Browser acceptance checks project request/query payloads and reload
persistence using fixtures; it does not establish model recall accuracy.
