# Automatic memory saving preferences

Integration patch v0.105.3 implements part of roadmap v0.116. Settings now has
**Review automatic memory saving**. Review the current value, choose whether to
allow automatic saving, confirm that exact setting, and press **Save memory saving
setting**. Changing the choice clears confirmation. Nothing is loaded or written
until the corresponding user action.

The preference persists in PostgreSQL for the existing local user. To preserve
existing installation behavior, a missing preference means **enabled, not yet
reviewed**. This is explicitly shown in the interface; it is not prior consent.
This patch does not introduce a default-off onboarding flow or comprehensive
privacy preferences. Manually saving a preference still requires individual
review through the existing saved-memory form.

A pause prevents subsequent automatic recognized fact, preference, correction,
project-fact, and task-outcome promotions. All production automatic promotion
calls share a per-user transaction lock with preference updates. An acknowledged
pause waits for promotions already running to finish; those earlier saves may
remain. A database/preference failure blocks automatic promotion and is handled
by the existing memory-failure path, rather than assuming permission to save.
The test-only in-memory store is not a production persistence path.

Pausing does not delete existing saved memories, prevent their retrieval, erase
chat history, disable conversation storage, or disable other knowledge/task
stores. Explicitly reviewed manual creates/corrections/deletions remain usable.
Retrieval may still update existing memory usage counters. Review and delete
existing saved records separately if desired. Other local users have independent
preference rows, but this API still exposes only the existing default user and
does not authenticate callers. Local project memory scopes are available in [v0.105.4](project-memory-scopes.md).
Multi-user authorization remains unfinished.

| Endpoint | Behavior |
| --- | --- |
| `GET /memories/preferences?project_id=<optional-project>` | `automatic_saving`, string `revision`, `reviewed`, local-user scope |
| `PATCH /memories/preferences?project_id=<optional-project>` | Strict boolean `automatic_saving`, reviewed `expected_revision`, literal `confirmed: true` |

Every successful update increments the revision, including repeated values, so
an old review cannot become valid again after pause/resume. Concurrent writes
with the same revision produce one success and one HTTP 409. Reload and review
after a conflict; neither API nor UI automatically retries. Requests inherit the
8 KiB memory body limit, fixed backend proxy, timeout and no-redirect behavior.
Unavailable databases return HTTP 503 without connection details.

Native PostgreSQL tests cover persistence, paused promotion, continued explicit
manual saving, resumed promotion, stale/concurrent changes, and an earlier
promotion delaying pause acknowledgement. Web tests and fixture-based Chromium
acceptance cover confirmation, exact revisions, reset and conflict behavior.
These checks do not establish semantic memory accuracy or hardware performance.
