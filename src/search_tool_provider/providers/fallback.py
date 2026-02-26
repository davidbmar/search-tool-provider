"""Fallback provider — multi-provider with automatic failover."""

from __future__ import annotations

import logging
import os
from typing import Any

from ..exceptions import SearchProviderError
from ..models import ProviderInfo, SearchResponse
from ..provider import SearchProvider
from ..utils import TTLCache

logger = logging.getLogger(__name__)

# Priority order and their env var keys
_ENV_KEYS: list[tuple[str, str]] = [
    ("serper", "SERPER_API_KEY"),
    ("tavily", "TAVILY_API_KEY"),
    ("brave", "BRAVE_API_KEY"),
    ("bing", "BING_API_KEY"),
    # google_cse needs two keys, handled separately
]


class FallbackProvider(SearchProvider):
    """Tries multiple providers in order, falling back on failure.

    Args:
        providers: List of (provider_name, kwargs) tuples.
        cache_ttl: TTL cache duration in seconds. 0 disables caching.
    """

    def __init__(
        self,
        providers: list[tuple[str, dict[str, Any]]] | None = None,
        cache_ttl: float = 0,
    ) -> None:
        self._provider_specs = providers or []
        self._providers: list[SearchProvider] = []
        self._cache = TTLCache(ttl=cache_ttl) if cache_ttl > 0 else None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazily instantiate providers on first use."""
        if self._initialized:
            return
        self._initialized = True

        from ..registry import get_provider

        for name, kwargs in self._provider_specs:
            try:
                provider = get_provider(name, **kwargs)
                self._providers.append(provider)
                logger.info("Fallback: loaded provider %s", name)
            except Exception as exc:
                logger.warning("Fallback: skipping provider %s: %s", name, exc)

        if not self._providers:
            raise SearchProviderError(
                "No providers available in fallback chain. "
                "Set at least one API key or install duckduckgo-search."
            )

    async def search(self, query: str, max_results: int = 10, **kwargs) -> SearchResponse:
        self._ensure_initialized()

        # Check cache
        if self._cache:
            key = TTLCache._make_key(query, max_results, **kwargs)
            cached = await self._cache.get(key)
            if cached is not None:
                return cached

        last_error: Exception | None = None
        for provider in self._providers:
            try:
                response = await provider.search(query, max_results=max_results, **kwargs)
                # Cache successful result
                if self._cache:
                    key = TTLCache._make_key(query, max_results, **kwargs)
                    await self._cache.set(key, response)
                return response
            except SearchProviderError as exc:
                logger.warning(
                    "Fallback: %s failed, trying next: %s",
                    type(provider).__name__,
                    exc,
                )
                last_error = exc

        raise SearchProviderError(
            f"All providers in fallback chain failed. Last error: {last_error}"
        )

    async def search_news(self, query: str, max_results: int = 5, **kwargs) -> SearchResponse:
        self._ensure_initialized()

        last_error: Exception | None = None
        for provider in self._providers:
            try:
                return await provider.search_news(query, max_results=max_results, **kwargs)
            except SearchProviderError as exc:
                logger.warning("Fallback news: %s failed: %s", type(provider).__name__, exc)
                last_error = exc

        raise SearchProviderError(
            f"All providers in fallback chain failed for news. Last error: {last_error}"
        )

    async def get_answer(self, query: str) -> str | None:
        self._ensure_initialized()

        for provider in self._providers:
            try:
                answer = await provider.get_answer(query)
                if answer:
                    return answer
            except SearchProviderError:
                continue
        return None

    async def get_provider_info(self) -> ProviderInfo:
        self._ensure_initialized()
        names = [type(p).__name__ for p in self._providers]
        return ProviderInfo(
            name="fallback",
            configured=bool(self._providers),
            api_key_set=True,
            features=["web", "news", "answer", "failover"],
            rate_limit_remaining=None,
        )

    @classmethod
    def from_env(cls, cache_ttl: float = 0) -> "FallbackProvider":
        """Build a fallback chain from available environment variables.

        Detects which API keys are set and builds the provider list
        in priority order. DuckDuckGo is always appended as final fallback.
        """
        specs: list[tuple[str, dict[str, Any]]] = []

        for name, env_key in _ENV_KEYS:
            if os.environ.get(env_key):
                specs.append((name, {}))

        # Google CSE needs both keys
        if os.environ.get("GOOGLE_CSE_API_KEY") and os.environ.get("GOOGLE_CSE_CX"):
            specs.append(("google_cse", {}))

        # DuckDuckGo as final fallback (no key needed)
        try:
            import duckduckgo_search  # noqa: F401
            specs.append(("duckduckgo", {}))
        except ImportError:
            pass

        if not specs:
            raise SearchProviderError(
                "No search providers configured. Set at least one API key "
                "(TAVILY_API_KEY, BRAVE_API_KEY, SERPER_API_KEY, BING_API_KEY) "
                "or install duckduckgo-search."
            )

        return cls(providers=specs, cache_ttl=cache_ttl)
