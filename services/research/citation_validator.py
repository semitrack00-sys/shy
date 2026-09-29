import re
from dataclasses import dataclass


_CITATION_TOKEN_PATTERN = re.compile(r"\[(.*?)\]")


@dataclass(frozen=True)
class CitationIssue:
    reference: str
    defect: str
    message: str


@dataclass(frozen=True)
class CitationValidationReport:
    is_valid: bool
    valid_references: tuple[int, ...]
    issues: tuple[CitationIssue, ...]


def validate_citation_references(
    text: str,
    sources: list[dict],
    require_url: bool = True,
) -> CitationValidationReport:
    indexed_sources: dict[int, dict] = {}

    for source in sources:
        try:
            ref_number = int(source.get("number"))
        except (TypeError, ValueError):
            continue

        indexed_sources[ref_number] = source

    issues: list[CitationIssue] = []
    valid: list[int] = []

    for token in _CITATION_TOKEN_PATTERN.findall(text):
        ref_text = token.strip()

        if not ref_text.isdigit():
            issues.append(
                CitationIssue(
                    reference=ref_text,
                    defect="CITATION_INVALID",
                    message="Citation reference is malformed.",
                )
            )
            continue

        ref_number = int(ref_text)
        source = indexed_sources.get(ref_number)

        if source is None:
            issues.append(
                CitationIssue(
                    reference=ref_text,
                    defect="CITATION_INVALID",
                    message="Citation points outside available evidence set.",
                )
            )
            continue

        if require_url:
            url = str(source.get("url", "")).strip()

            if not url.startswith(("http://", "https://")):
                issues.append(
                    CitationIssue(
                        reference=ref_text,
                        defect="CITATION_MISMATCH",
                        message="Citation source URL is missing or invalid.",
                    )
                )
                continue

        valid.append(ref_number)

    return CitationValidationReport(
        is_valid=(len(issues) == 0),
        valid_references=tuple(sorted(set(valid))),
        issues=tuple(issues),
    )
