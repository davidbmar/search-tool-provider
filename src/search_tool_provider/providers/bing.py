"""Bing Web Search provider — Microsoft Azure cognitive services."""

from __future__ import annotations

import os

import httpx

from ..exceptions import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    SearchTimeoutError,
)
from ..models import ProviderInfo, SearchResponse, SearchResult
from ..provider import SearchProvider
from ..utils import clean_html, normalize_scores

_BASE_URL = "https://api.bing.microsoft.com/v7.0"


class BingProvider(SearchProvider):
    """Search using the Bing Web Search API.

    Args:
        api_key: Bing subscription key. Falls back to BING_API_KEY env var.
        timeout: HTTP timeout in seconds (default 30).
    """

    def __init__(self, api_key: str | None = None, timeout: float = 30) -> None:
        self.api_key = api_key or os.environ.get("BING_API_KEY", "")
        if not self.api_key:
            raise AuthenticationError(
                "Bing API key required. Set BING_API_KEY or pass api_key="
            )
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 10, **kwargs) -> SearchResponse:
        params = {"q": query, "count": max_results}
        safe_search = kwargs.get("safe_search", True)
        if safe_search:
            params["safeSearch"] = "Moderate"

        data = await self._get("/search", params)

        results = [
            SearchResult(
                title=r.get("name", ""),
                url=r.get("url", ""),
                snippet=clean_html(r.get("snippet", "")),
                source="bing",
                raw=r,
            )
            for r in data.get("webPages", {}).get("value", [])
        ]
        normalize_scores(results)

        total = data.get("webPages", {}).get("totalEstimatedMatches")

        return SearchResponse(
            results=results,
            query=query,
            provider="bing",
            total_results=total,
        )

    async def search_news(self, query: str, max_results: int = 5, **kwargs) -> SearchResponse:
        params = {"q": query, "count": max_results}
        data = await self._get("/news/search", params)

        results = [
            SearchResult(
                title=r.get("name", ""),
                url=r.get("url", ""),
                snippet=clean_html(r.get("description", "")),
                source="bing",
                raw=r,
            )
            for r in data.get("value", [])
        ]
        normalize_scores(results)

        return SearchResponse(results=results, query=query, provider="bing")

    async def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="bing",
            configured=True,
            api_key_set=bool(self.api_key),
            features=["web", "news"],
        )

    async def _get(self, path: str, params: dict) -> dict:
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{_BASE_URL}{path}", params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError(f"Bing request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Bing request failed: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Invalid Bing API key")
        if resp.status_code == 429:
            retry = resp.headers.get("Retry-After")
            raise RateLimitError(
                "Bing rate limit exceeded",
                retry_after=float(retry) if retry else None,
            )
        if resp.status_code >= 400:
            raise ProviderUnavailableError(f"Bing error {resp.status_code}: {resp.text}")

        return resp.json()
