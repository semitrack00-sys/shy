from dataclasses import asdict, dataclass
from typing import Any


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
            if not result.url.startswith(
                ("http://", "https://")
            ):
                continue

            normalized.append(asdict(result))

        return {
            "provider": self.provider.name,
            "query": clean_query,
            "result_count": len(normalized),
            "results": normalized,
        }
