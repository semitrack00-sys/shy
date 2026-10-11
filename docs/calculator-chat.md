# Calculator-backed chat — v0.105.8

Use `Calculate 0.1 + 0.2`, `What is 17% of 842?`, or an explicit expression such
as `(2 + 3) * 4`. Both `/agent` (the web chat entry point) and `/chat` compute the
answer through the read-only calculator and existing conversation ownership
checks. The reply is saved alongside the user's message. No language model or
web provider produces the numerical result. Cross-project conversation reuse
is rejected; local project scopes remain organization scopes, not authentication.

Supported operators are `+`, `-`, `*`, `/`, `//`, `%` (modulo), and `**`, with
parentheses and signed decimal numbers. `17% of 842` is explicitly converted to
`17 * 842 / 100`. Floor division and modulo use floor semantics, including for
negative numbers. Decimal calculations use 28 significant digits. Repeating
fractions may be rounded; this is not arbitrary precision or unit-aware math.
The additional `decimal_result` string is used for chat display. The existing
numeric `result` field remains for tool-client compatibility.

Bounds: 256 expression characters, 64 AST nodes, 16 levels of nesting, numeric
literals with at most 24 digits, and integer exponents from -12 to 12. Each parsed literal and operator result with nonzero magnitude must be between 1e-24 and 1e24. Division by zero,
non-finite results, oversized/unsupported syntax and partial expressions fail
with invalid arguments. Evaluation walks permitted AST nodes; it never invokes
Python eval, imports, function calls, variables or shell commands.

SHY does not extract a percentage from a longer request and silently ignore the
remainder. Explicit Calculate/Compute requests with invalid syntax fail without
model guessing or running embedded actions. Ordinary questions containing years
or prices are not automatically treated as formulas. Currency symbols, thousands
separators, inferred units and general word problems are unsupported. A result
does not verify user-supplied assumptions or amount units.

Tests check decimal sums, precedence, percentages, negative floor/modulo,
repeating fractions, rejected code/partial inputs and resource limits. A separate
PostgreSQL acceptance script calls the real HTTP agent/chat handlers, verifies
saved user/assistant turns and project isolation, and prevents model generation
from replacing calculator results. These are arithmetic and integration checks,
not the full research/reasoning quality benchmark v0.150.

The v0.105.9 refinement uses exact bounded rational operands for floor division and modulo so rounding a decimal quotient cannot change the quotient floor or erase its remainder near an integer boundary. Other decimal operations retain their stated precision limit.
