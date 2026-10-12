"""Bounded ordered logical-line previews; never an executable or minimal patch."""
from difflib import SequenceMatcher

MAX_LINES = 1000
MAX_HUNKS = 10
MAX_SAMPLE_LINES = 2
MAX_LINE_CHARS = 150


def ordered_preview(left: str, right: str) -> dict:
    if not isinstance(left, str) or not isinstance(right, str) or max(len(left), len(right)) > 100_000:
        return {"status": "unavailable", "reason": "ordered_text_character_limit", "line_limit": MAX_LINES}
    old, new = left.splitlines(), right.splitlines()
    if max(len(old), len(new)) > MAX_LINES:
        return {"status": "unavailable", "reason": "ordered_logical_line_limit", "line_limit": MAX_LINES}
    # At most one million pairs of logical lines; repeated lines are retained.
    ops = SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
    changed = [op for op in ops if op[0] != "equal"]

    def side(lines, start, end):
        return {"start_line": start + 1, "line_count": end - start,
                "samples": [{"line": i + 1, "text": lines[i][:MAX_LINE_CHARS],
                             "truncated": len(lines[i]) > MAX_LINE_CHARS}
                            for i in range(start, min(end, start + MAX_SAMPLE_LINES))],
                "omitted_lines": max(0, end - start - MAX_SAMPLE_LINES)}

    hunks = [{"kind": tag, "left": side(old, i1, i2), "right": side(new, j1, j2)}
             for tag, i1, i2, j1, j2 in changed[:MAX_HUNKS]]
    return {"status": "evaluated", "method": "ordered_logical_lines", "line_limit": MAX_LINES,
            "left_line_count": len(old), "right_line_count": len(new),
            "inserted_lines": sum(j2-j1 for tag, i1, i2, j1, j2 in changed),
            "deleted_lines": sum(i2-i1 for tag, i1, i2, j1, j2 in changed),
            "equal_lines": sum(i2-i1 for tag, i1, i2, j1, j2 in ops if tag == "equal"),
            "text_identical": left == right, "line_sequence_equal": old == new,
            "line_endings_compared": False, "semantic_equivalence_checked": False,
            "minimal_patch_guaranteed": False, "change_hunk_count": len(changed), "hunks": hunks,
            "omitted_hunks": max(0, len(changed) - MAX_HUNKS),
            "preview_truncated": len(changed) > MAX_HUNKS or any(
                s["omitted_lines"] or any(row["truncated"] for row in s["samples"])
                for h in hunks for s in (h["left"], h["right"])),
            "hunk_limit": MAX_HUNKS, "sample_lines_per_side": MAX_SAMPLE_LINES,
            "sample_character_limit": MAX_LINE_CHARS}
