from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryContext:
    repository_identifier: str
    branch: str
    commit: str
    relevant_files: tuple[str, ...]
    diagnostics: tuple[str, ...]
    test_results: tuple[str, ...]
    diff_summary: str


def build_repository_context(
    repository_identifier: str,
    branch: str,
    commit: str,
    relevant_files: list[str] | tuple[str, ...] | None = None,
    diagnostics: list[str] | tuple[str, ...] | None = None,
    test_results: list[str] | tuple[str, ...] | None = None,
    diff_summary: str = "",
) -> RepositoryContext:
    files = _sanitize_list(relevant_files, max_items=60, max_item_chars=240)
    diag = _sanitize_list(diagnostics, max_items=80, max_item_chars=300)
    tests = _sanitize_list(test_results, max_items=80, max_item_chars=220)

    return RepositoryContext(
        repository_identifier=str(repository_identifier or "").strip(),
        branch=str(branch or "").strip(),
        commit=str(commit or "").strip(),
        relevant_files=files,
        diagnostics=diag,
        test_results=tests,
        diff_summary=_normalize_text(diff_summary, max_chars=4000),
    )


def _sanitize_list(
    values: list[str] | tuple[str, ...] | None,
    max_items: int,
    max_item_chars: int,
) -> tuple[str, ...]:
    output: list[str] = []

    for raw in values or ():
        normalized = _normalize_text(raw, max_chars=max_item_chars)
        if not normalized:
            continue
        output.append(normalized)
        if len(output) >= max_items:
            break

    return tuple(output)


def _normalize_text(value: str, max_chars: int) -> str:
    normalized = " ".join(str(value or "").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."
