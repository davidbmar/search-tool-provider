"""DuckDuckGo search provider — free, no API key required."""

from __future__ import annotations

import asyncio
from functools import partial

from ..exceptions import ProviderUnavailableError, SearchTimeoutError
from ..models import ProviderInfo, SearchResponse, SearchResult
from ..provider import SearchProvider
from ..utils import normalize_scores

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None  # type: ignore[assignment,misc]


class DuckDuckGoProvider(SearchProvider):
    """Search using DuckDuckGo (no API key needed).

    Requires: pip install search-tool-provider[duckduckgo]
    """

    def __init__(self) -> None:
        if DDGS is None:
            raise ImportError(
                "duckduckgo-search is required. "
                "Install with: pip install search-tool-provider[duckduckgo]"
            )

    async def search(self, query: str, max_results: int = 10, **kwargs) -> SearchResponse:
        loop = asyncio.get_running_loop()
        try:
            raw_results = await loop.run_in_executor(
                None, partial(self._sync_search, query, max_results, **kwargs)
            )
        except Exception as exc:
            if "Ratelimit" in str(exc) or "429" in str(exc):
                raise SearchTimeoutError(f"DuckDuckGo rate limited: {exc}") from exc
            raise ProviderUnavailableError(f"DuckDuckGo search failed: {exc}") from exc

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", r.get("url", "")),
                snippet=r.get("body", ""),
                source="duckduckgo",
                raw=r,
            )
            for r in raw_results
        ]
        normalize_scores(results)

        return SearchResponse(
            results=results,
            query=query,
            provider="duckduckgo",
        )

    async def search_news(self, query: str, max_results: int = 5, **kwargs) -> SearchResponse:
        loop = asyncio.get_running_loop()
        try:
            raw_results = await loop.run_in_executor(
                None, partial(self._sync_news, query, max_results)
            )
        except Exception as exc:
            raise ProviderUnavailableError(f"DuckDuckGo news search failed: {exc}") from exc

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", r.get("href", "")),
                snippet=r.get("body", ""),
                source="duckduckgo",
                published_date=None,
                raw=r,
            )
            for r in raw_results
        ]
        normalize_scores(results)

        return SearchResponse(results=results, query=query, provider="duckduckgo")

    async def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="duckduckgo",
            configured=True,
            api_key_set=True,  # no key needed
            features=["web", "news"],
        )

    @staticmethod
    def _sync_search(query: str, max_results: int, **kwargs) -> list[dict]:
        region = kwargs.get("region", "wt-wt")
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results, region=region))

    @staticmethod
    def _sync_news(query: str, max_results: int) -> list[dict]:
        with DDGS() as ddgs:
            return list(ddgs.news(query, max_results=max_results))
