"""Tavily search provider — AI-optimized search with direct answers."""

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
from ..utils import clean_html

_BASE_URL = "https://api.tavily.com"


class TavilyProvider(SearchProvider):
    """Search using the Tavily API.

    Args:
        api_key: Tavily API key. Falls back to TAVILY_API_KEY env var.
        timeout: HTTP timeout in seconds (default 30).
    """

    def __init__(self, api_key: str | None = None, timeout: float = 30) -> None:
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY", "")
        if not self.api_key:
            raise AuthenticationError(
                "Tavily API key required. Set TAVILY_API_KEY or pass api_key="
            )
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 10, **kwargs) -> SearchResponse:
        include_answer = kwargs.get("include_answer", False)
        payload = {
            "query": query,
            "max_results": max_results,
            "include_answer": include_answer,
        }

        data = await self._post("/search", payload)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=clean_html(r.get("content", "")),
                source="tavily",
                score=r.get("score", 0.0),
                raw=r,
            )
            for r in data.get("results", [])
        ]

        return SearchResponse(
            results=results,
            query=query,
            provider="tavily",
            answer=data.get("answer"),
        )

    async def get_answer(self, query: str) -> str | None:
        payload = {
            "query": query,
            "max_results": 3,
            "include_answer": True,
        }
        data = await self._post("/search", payload)
        return data.get("answer")

    async def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="tavily",
            configured=True,
            api_key_set=bool(self.api_key),
            features=["web", "answer"],
        )

    async def _post(self, path: str, payload: dict) -> dict:
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{_BASE_URL}{path}", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError(f"Tavily request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Tavily request failed: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Invalid Tavily API key")
        if resp.status_code == 429:
            raise RateLimitError("Tavily rate limit exceeded")
        if resp.status_code >= 400:
            raise ProviderUnavailableError(f"Tavily error {resp.status_code}: {resp.text}")

        return resp.json()
