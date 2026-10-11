# Research citation membership — v0.105.9

Generated research answers now require numeric citations that refer to the
retrieved evidence inventory. The actual synthesis path rejects uncited output,
malformed or nonexistent references, and answer URLs outside the evidence set.
It fails safely rather than returning the rejected model answer.

Prompt numbering is bound to the displayed source table by URL, even when the
source table and evidence order differ. Source numbers must be unique and
contiguous and the table must match the evidence URL inventory. Invalid evidence
fails before model generation. Up to twelve evidence items, a 20,000-character
answer and one hundred citation tokens are accepted.

Sources must have syntactically public HTTP(S) URLs without credentials, unusual
ports, whitespace or backslashes. Private literal IPs, localhost, local/internal
suffixes and malformed hosts are rejected. This is URL validation, not DNS
resolution or a direct-page fetch. Public domains are not independently trusted
or authenticated. Source cards suppress malformed and non-HTTP links.

Research still requires a configured search provider and local generation model.
The core does not install credentials or prove live provider availability through
fixture tests. The existing prompt labels source material as untrusted evidence
and forbids treating source instructions as commands.

Membership validation does **not** prove a claim is supported, establish source
truth or authority, check publication dates, or compare semantic disagreements.
A model can cite a real source incorrectly. Those quality/freshness measurements
and full-page retrieval remain roadmap work. Unsupported generated answers can
fail conservatively, including answers with non-numeric bracket syntax.

Automated checks exercise the validator and actual HTTP agent/synthesis functions
with fixture search/model responses, including rejected output and reordered
source numbering. Fixture assertions are integration evidence, not real-world
research accuracy measurements.
