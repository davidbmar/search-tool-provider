"""Brave Search provider — privacy-focused with rich infoboxes."""

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

_BASE_URL = "https://api.search.brave.com/res/v1"


class BraveProvider(SearchProvider):
    """Search using the Brave Search API.

    Args:
        api_key: Brave API key. Falls back to BRAVE_API_KEY env var.
        timeout: HTTP timeout in seconds (default 30).
    """

    def __init__(self, api_key: str | None = None, timeout: float = 30) -> None:
        self.api_key = api_key or os.environ.get("BRAVE_API_KEY", "")
        if not self.api_key:
            raise AuthenticationError(
                "Brave API key required. Set BRAVE_API_KEY or pass api_key="
            )
        self.timeout = timeout
        self._rate_limit_remaining: int | None = None

    async def search(self, query: str, max_results: int = 10, **kwargs) -> SearchResponse:
        params = {"q": query, "count": max_results}
        data, headers = await self._get("/web/search", params)

        self._rate_limit_remaining = _parse_int(headers.get("x-ratelimit-remaining"))

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=clean_html(r.get("description", "")),
                source="brave",
                raw=r,
            )
            for r in data.get("web", {}).get("results", [])
        ]
        normalize_scores(results)

        # Extract infobox as knowledge_graph
        knowledge_graph = None
        infobox = data.get("infobox")
        if infobox:
            knowledge_graph = {
                "title": infobox.get("title", ""),
                "description": infobox.get("description", ""),
                "facts": infobox.get("facts", []),
            }

        return SearchResponse(
            results=results,
            query=query,
            provider="brave",
            knowledge_graph=knowledge_graph,
        )

    async def search_news(self, query: str, max_results: int = 5, **kwargs) -> SearchResponse:
        params = {"q": query, "count": max_results}
        data, _ = await self._get("/news/search", params)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=clean_html(r.get("description", "")),
                source="brave",
                raw=r,
            )
            for r in data.get("results", [])
        ]
        normalize_scores(results)

        return SearchResponse(results=results, query=query, provider="brave")

    async def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="brave",
            configured=True,
            api_key_set=bool(self.api_key),
            features=["web", "news", "infobox"],
            rate_limit_remaining=self._rate_limit_remaining,
        )

    async def _get(self, path: str, params: dict) -> tuple[dict, httpx.Headers]:
        headers = {
            "X-Subscription-Token": self.api_key,
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{_BASE_URL}{path}", params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError(f"Brave request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Brave request failed: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Invalid Brave API key")
        if resp.status_code == 429:
            retry = _parse_int(resp.headers.get("retry-after"))
            raise RateLimitError("Brave rate limit exceeded", retry_after=retry)
        if resp.status_code >= 400:
            raise ProviderUnavailableError(f"Brave error {resp.status_code}: {resp.text}")

        return resp.json(), resp.headers


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
