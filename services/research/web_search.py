from dataclasses import asdict, dataclass
from typing import Any


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str


class WebSearchError(RuntimeError):
    """Raised when SHY's web research provider cannot complete a search."""


class WebSearchProvider:
    """
    Provider-independent contract for SHY web research.

    Providers must return structured public information only.
    They do not execute browser actions or perform write operations.
    """

    name = "unconfigured"

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchResult]:
        raise NotImplementedError


class WebSearchService:
    """
    Controlled read-only research service.

    This layer normalizes provider results before they enter SHY.
    """

    def __init__(self, provider: WebSearchProvider):
        self.provider = provider

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> dict[str, Any]:
        clean_query = query.strip()

        if not clean_query:
            raise ValueError("Search query cannot be empty.")

        if max_results < 1 or max_results > 10:
            raise ValueError(
                "max_results must be between 1 and 10."
            )

        results = self.provider.search(
            clean_query,
            max_results=max_results,
        )

        normalized = []

        for result in results[:max_results]:
            clean_url = _normalize_text(result.url)

            if not clean_url.startswith(
                ("http://", "https://")
            ):
                continue

            clean_title = _normalize_text(result.title)
            clean_source = _normalize_text(result.source)
            clean_snippet = _normalize_text(result.snippet)

            normalized_result = SearchResult(
                title=clean_title or clean_url,
                url=clean_url,
                snippet=clean_snippet,
                source=clean_source or "unknown",
            )

            normalized.append(asdict(normalized_result))

        return {
            "provider": self.provider.name,
            "query": clean_query,
            "result_count": len(normalized),
            "results": normalized,
        }
