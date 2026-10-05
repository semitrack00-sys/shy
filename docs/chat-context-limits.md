# Ordinary chat history budgets

Integration patch v0.105.2 implements the bounded-context part of roadmap v0.119
early. It fixes two ordinary chat-history paths that could exceed their configured
limits: the first oversized selected record and the recent-message fallback used
when lexical retrieval selected no history.

Before ordinary chat history reaches downstream generation, the loader now caps:

| Context source | Maximum characters | Maximum messages |
| --- | ---: | ---: |
| Selected durable memory | 1,200 | 4 |
| Conversation history, including fallback | 3,200 | 20 |

Recent messages are retained first and returned in chronological order. If a
boundary message is too large, its excerpt includes `[Context excerpt truncated]`
inside the same character budget. Older messages can be omitted. Unsupported
message roles are discarded; permitted roles remain unchanged. Existing prompt
safety filtering still runs before these excerpts are prepared.

The combined ordinary-history maximum is 4,400 characters. This is not a token
limit, does not bound the current incoming user message, and does not guarantee
that every model's context window can hold the final prompt. Separate task/workflow
context construction and research source budgets remain separate mechanisms.
This change does not increase the model context window, summarize history with a
model, or guarantee recall of all facts from long conversations.

The memory loader reports memory as used only when its bounded result is nonempty.
Health advertises the ordinary-history limits and these distinctions. The existing
memory selectors can still report their own candidate/selection diagnostics;
the new guard is the final bound in the ordinary chat history loader.

Tests cover a 100,000-character fallback message, an oversized selected record,
oversized durable memory, empty context, chronology, message limits, allowed roles,
Unicode character accounting, and zero/tiny budgets. The full-runtime release gate
calls the actual history loader with controlled source records. These are behavior
checks, not measurements of model recall or long-conversation answer quality.
