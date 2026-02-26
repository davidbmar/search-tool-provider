"""Serper provider — Google SERP data with knowledge graph and answer box."""

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

_BASE_URL = "https://google.serper.dev"


class SerperProvider(SearchProvider):
    """Search using the Serper.dev Google SERP API.

    Args:
        api_key: Serper API key. Falls back to SERPER_API_KEY env var.
        timeout: HTTP timeout in seconds (default 30).
    """

    def __init__(self, api_key: str | None = None, timeout: float = 30) -> None:
        self.api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        if not self.api_key:
            raise AuthenticationError(
                "Serper API key required. Set SERPER_API_KEY or pass api_key="
            )
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 10, **kwargs) -> SearchResponse:
        payload = {"q": query, "num": max_results}
        data = await self._post("/search", payload)
        return self._parse_response(data, query)

    async def search_news(self, query: str, max_results: int = 5, **kwargs) -> SearchResponse:
        payload = {"q": query, "num": max_results, "type": "news"}
        data = await self._post("/search", payload)

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=clean_html(r.get("snippet", "")),
                source="serper",
                raw=r,
            )
            for r in data.get("news", [])
        ]
        normalize_scores(results)

        return SearchResponse(results=results, query=query, provider="serper")

    async def get_answer(self, query: str) -> str | None:
        payload = {"q": query, "num": 3}
        data = await self._post("/search", payload)

        # Check answer box first, then knowledge graph
        answer_box = data.get("answerBox", {})
        if answer_box:
            answer = answer_box.get("answer") or answer_box.get("snippet")
            if answer:
                return answer
            # List-type answer box
            items = answer_box.get("list")
            if items:
                return "\n".join(f"- {item}" for item in items[:5])

        kg = data.get("knowledgeGraph", {})
        if kg and kg.get("description"):
            return kg["description"]

        return None

    async def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="serper",
            configured=True,
            api_key_set=bool(self.api_key),
            features=["web", "news", "answer", "knowledge_graph"],
        )

    def _parse_response(self, data: dict, query: str) -> SearchResponse:
        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=clean_html(r.get("snippet", "")),
                source="serper",
                raw=r,
            )
            for r in data.get("organic", [])
        ]
        normalize_scores(results)

        # Extract answer from answer box
        answer = None
        answer_box = data.get("answerBox", {})
        if answer_box:
            answer = answer_box.get("answer") or answer_box.get("snippet")

        # Extract knowledge graph
        knowledge_graph = None
        kg = data.get("knowledgeGraph", {})
        if kg:
            knowledge_graph = {
                "title": kg.get("title", ""),
                "type": kg.get("type", ""),
                "description": kg.get("description", ""),
                "attributes": kg.get("attributes", {}),
            }

        return SearchResponse(
            results=results,
            query=query,
            provider="serper",
            answer=answer,
            knowledge_graph=knowledge_graph,
        )

    async def _post(self, path: str, payload: dict) -> dict:
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{_BASE_URL}{path}", json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError(f"Serper request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Serper request failed: {exc}") from exc

        if resp.status_code == 401:
            raise AuthenticationError("Invalid Serper API key")
        if resp.status_code == 429:
            raise RateLimitError("Serper rate limit exceeded")
        if resp.status_code >= 400:
            raise ProviderUnavailableError(f"Serper error {resp.status_code}: {resp.text}")

        return resp.json()
