# Multilingual research date rules

v0.105.18 extends research date gates with fixed French and Haitian Creole phrases. It does not measure general language understanding or source truth.

| Window in UTC calendar days | English phrases | French phrases | Haitian Creole phrases |
| --- | --- | --- | --- |
| 0 | today; right now | aujourd’hui; en ce moment | jodi a; jodia; kounye a |
| 7 | latest; current; recent; this week; up to date | cette semaine; récent/récente/récents/récentes; dernières nouvelles; à jour | semèn sa a; dènye nouvèl; dènye enfòmasyon |

Matching normalizes Unicode NFKC, letter case, curly apostrophes and whitespace. Unicode word boundaries prevent matching longer words. Multiple matching rules choose the shortest window; the recorded basis describes the rules selecting that window, with `mixed_hint` when multiple languages select the same minimum. No match returns `no_window` and no freshness requirement. These rules do not interpret negation, quoted text, historical intent or arbitrary synonyms. UTC days are calendar days, not rolling 24-hour intervals or the user’s timezone.

Actual chat and agent research paths apply the window before generation and to cited sources afterward. Missing, stale, invalid or future provider date estimates cannot authorize a current answer. Retrieval time never substitutes for a provider date. Public answer metadata includes `date_window_basis`, shown in the existing answer context and retained by chat history. Older metadata without a basis displays that the origin was not recorded.

The fixed reasoning benchmark now contains 45 reference cases. These checks cover deterministic rules, not live-model quality, independent publication dates or representative multilingual research accuracy. Sequential qualification and v0.150 remain incomplete.
