"""Abstract base class for search providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ProviderInfo, SearchResponse


class SearchProvider(ABC):
    """Base class that all search providers must implement.

    Required:
        search() — run a web search query.

    Optional (have default implementations):
        search_news() — search news articles (defaults to regular search).
        get_answer() — get a direct answer (defaults to None).
        get_provider_info() — return provider status info.
    """

    @abstractmethod
    async def search(self, query: str, max_results: int = 10, **kwargs) -> SearchResponse:
        """Run a web search.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return.
            **kwargs: Provider-specific options (language, region, time_range, etc.)

        Returns:
            SearchResponse with results and metadata.

        Raises:
            AuthenticationError: Bad or missing API key.
            RateLimitError: Quota exceeded.
            SearchTimeoutError: Provider didn't respond.
            ProviderUnavailableError: Backend is down.
        """

    async def search_news(self, query: str, max_results: int = 5, **kwargs) -> SearchResponse:
        """Search news articles.

        Default implementation delegates to search(). Override if the
        provider has a dedicated news endpoint.

        Args:
            query: The search query string.
            max_results: Maximum number of results.

        Returns:
            SearchResponse with news results.
        """
        return await self.search(query, max_results=max_results, **kwargs)

    async def get_answer(self, query: str) -> str | None:
        """Get a direct answer to a question.

        Default returns None. Override if the provider supports
        direct answers (e.g. Tavily, Serper answer box).

        Args:
            query: The question to answer.

        Returns:
            Answer string, or None if not supported.
        """
        return None

    async def get_provider_info(self) -> ProviderInfo:
        """Return status information about this provider.

        Default returns basic info. Override to add features,
        rate limit status, etc.

        Returns:
            ProviderInfo with name and configuration status.
        """
        return ProviderInfo(name=self.__class__.__name__, configured=True)
