import os

import httpx

from .web_search import (
    SearchResult,
    WebSearchError,
    WebSearchProvider,
)


class TavilySearchProvider(WebSearchProvider):
    """
    Tavily implementation of SHY's read-only web search contract.
    """

    name = "tavily"

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 20.0,
    ):
        self.api_key = (
            api_key
            or os.getenv("TAVILY_API_KEY", "")
        ).strip()

        if not self.api_key:
            raise WebSearchError(
                "TAVILY_API_KEY is not configured."
            )

        self.timeout_seconds = timeout_seconds

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchResult]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }

        try:
            response = httpx.post(
                "https://api.tavily.com/search",
                json=payload,
                timeout=self.timeout_seconds,
            )

            response.raise_for_status()
            data = response.json()

        except (
            httpx.HTTPError,
            ValueError,
        ) as exc:
            raise WebSearchError(
                "Tavily search failed."
            ) from exc

        results = []

        for item in data.get("results", []):
            url = str(
                item.get("url", "")
            ).strip()

            title = str(
                item.get("title", "")
            ).strip()

            snippet = str(
                item.get("content", "")
            ).strip()

            if not url:
                continue

            results.append(
                SearchResult(
                    title=title or url,
                    url=url,
                    snippet=snippet,
                    source=self._source_from_url(url),
                )
            )

        return results

    @staticmethod
    def _source_from_url(url: str) -> str:
        try:
            return httpx.URL(url).host or url
        except Exception:
            return url
