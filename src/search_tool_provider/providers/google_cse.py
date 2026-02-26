"""Google Custom Search Engine provider."""

from __future__ import annotations

import asyncio
import os
from functools import partial

from ..exceptions import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
)
from ..models import ProviderInfo, SearchResponse, SearchResult
from ..provider import SearchProvider
from ..utils import clean_html, normalize_scores

try:
    from googleapiclient.discovery import build as google_build
    from googleapiclient.errors import HttpError
except ImportError:
    google_build = None  # type: ignore[assignment,misc]
    HttpError = Exception  # type: ignore[assignment,misc]


class GoogleCSEProvider(SearchProvider):
    """Search using Google Custom Search Engine API.

    Args:
        api_key: Google API key. Falls back to GOOGLE_CSE_API_KEY env var.
        cx: Custom Search Engine ID. Falls back to GOOGLE_CSE_CX env var.
    """

    def __init__(self, api_key: str | None = None, cx: str | None = None) -> None:
        if google_build is None:
            raise ImportError(
                "google-api-python-client is required. "
                "Install with: pip install search-tool-provider[google]"
            )
        self.api_key = api_key or os.environ.get("GOOGLE_CSE_API_KEY", "")
        self.cx = cx or os.environ.get("GOOGLE_CSE_CX", "")
        if not self.api_key:
            raise AuthenticationError(
                "Google CSE API key required. Set GOOGLE_CSE_API_KEY or pass api_key="
            )
        if not self.cx:
            raise AuthenticationError(
                "Google CSE CX required. Set GOOGLE_CSE_CX or pass cx="
            )
        self._service = google_build("customsearch", "v1", developerKey=self.api_key)

    async def search(self, query: str, max_results: int = 10, **kwargs) -> SearchResponse:
        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(
                None, partial(self._sync_search, query, max_results)
            )
        except HttpError as exc:
            status = getattr(exc, "status_code", None) or getattr(exc.resp, "status", 0)
            if status == 403:
                raise RateLimitError("Google CSE daily quota exceeded") from exc
            if status == 401:
                raise AuthenticationError("Invalid Google CSE API key") from exc
            raise ProviderUnavailableError(f"Google CSE error: {exc}") from exc

        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=clean_html(r.get("snippet", "")),
                source="google_cse",
                raw=r,
            )
            for r in data.get("items", [])
        ]
        normalize_scores(results)

        total = int(data.get("searchInformation", {}).get("totalResults", 0))

        return SearchResponse(
            results=results,
            query=query,
            provider="google_cse",
            total_results=total,
        )

    async def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="google_cse",
            configured=True,
            api_key_set=bool(self.api_key),
            features=["web"],
        )

    def _sync_search(self, query: str, max_results: int) -> dict:
        return (
            self._service.cse()
            .list(q=query, cx=self.cx, num=min(max_results, 10))
            .execute()
        )
