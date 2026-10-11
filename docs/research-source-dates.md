# Research source dates — v0.105.10

SHY requests Tavily's optional `published_date` and retains it as a **provider publication or update estimate**. It is not a verified publication timestamp. SHY separately stamps the UTC time it received search results; retrieval never establishes when a page was published or whether its claims are true.

The research engine carries both fields into evidence and source tables. The synthesis guard accepts bounded ISO dates, timezone-aware ISO timestamps and RFC 2822 timestamps with an explicit GMT or numeric offset. Missing, invalid and future estimates cannot qualify as recent. Date-only estimates use UTC calendar days. Timestamp comparisons respect timezone offsets. The source cards display estimated dates and retrieval times separately.

Conservative English hints select a date window: `today` and `right now` require the current UTC date; `latest`, `current`, `recent`, `this week` and `up to date` allow seven UTC calendar days. With no detected recency hint, thirty days is an informational classification only: historical and undated research remains allowed. These heuristics can overmatch words such as electrical “current”; they are not universal intent or multilingual detection.

For a detected current-information request, no qualifying source produces a deterministic clarification before model generation. When fresh and older sources coexist, the prompt identifies eligible references and the answer must cite only those references, in addition to existing citation membership and URL checks. Duplicate URLs cannot override a stale row with a fresh row. This checks citation date eligibility, not whether each claim is semantically supported or current.

The `/agent` research response exposes date metadata when supplied by search. Older fixture responses retain their existing source shape. Ordinary `/chat` research also uses the synthesis date gate, though it does not yet expose source cards in its response.

Validation includes parser boundary cases, separate retrieval timestamps, provider request fixtures, full engine propagation, mixed citation eligibility, actual agent HTTP calls against disposable PostgreSQL, and web rendering. Live Tavily credentials, verified full-page dates, real-model answer quality and the v0.150 research benchmark remain unqualified.

Provider contract: https://docs.tavily.com/documentation/api-reference/endpoint/search (`include_published_date`, beta estimated publication or last-update date).
