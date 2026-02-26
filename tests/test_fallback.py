"""Tests for the FallbackProvider."""

import pytest

from search_tool_provider.exceptions import ProviderUnavailableError, SearchProviderError
from search_tool_provider.models import SearchResponse, SearchResult
from search_tool_provider.provider import SearchProvider
from search_tool_provider.providers.fallback import FallbackProvider
from search_tool_provider.registry import register_provider, _registry


class _GoodProvider(SearchProvider):
    async def search(self, query, max_results=10, **kwargs):
        return SearchResponse(
            results=[SearchResult("Good", "http://good.com", source="good")],
            query=query,
            provider="good",
        )

    async def get_answer(self, query):
        return "good answer"


class _BadProvider(SearchProvider):
    async def search(self, query, max_results=10, **kwargs):
        raise ProviderUnavailableError("I'm down")

    async def get_answer(self, query):
        raise ProviderUnavailableError("I'm down")


class TestFallback:
    def setup_method(self):
        register_provider("_test_good", _GoodProvider)
        register_provider("_test_bad", _BadProvider)

    def teardown_method(self):
        _registry.pop("_test_good", None)
        _registry.pop("_test_bad", None)

    async def test_first_provider_succeeds(self):
        fb = FallbackProvider(providers=[("_test_good", {}), ("_test_bad", {})])
        result = await fb.search("test")
        assert result.provider == "good"

    async def test_failover_to_second(self):
        fb = FallbackProvider(providers=[("_test_bad", {}), ("_test_good", {})])
        result = await fb.search("test")
        assert result.provider == "good"

    async def test_all_fail_raises(self):
        fb = FallbackProvider(providers=[("_test_bad", {})])
        with pytest.raises(SearchProviderError, match="All providers"):
            await fb.search("test")

    async def test_get_answer_failover(self):
        fb = FallbackProvider(providers=[("_test_bad", {}), ("_test_good", {})])
        answer = await fb.get_answer("question")
        assert answer == "good answer"

    async def test_get_answer_all_fail_returns_none(self):
        fb = FallbackProvider(providers=[("_test_bad", {})])
        answer = await fb.get_answer("question")
        assert answer is None

    async def test_caching(self):
        fb = FallbackProvider(providers=[("_test_good", {})], cache_ttl=300)
        r1 = await fb.search("cached query")
        r2 = await fb.search("cached query")
        assert r1.provider == r2.provider

    async def test_provider_info(self):
        fb = FallbackProvider(providers=[("_test_good", {})])
        info = await fb.get_provider_info()
        assert info.name == "fallback"
        assert "failover" in info.features

    def test_from_env_with_duckduckgo(self):
        """DuckDuckGo should always be available as fallback."""
        import os
        with pytest.MonkeyPatch.context() as mp:
            mp.delenv("TAVILY_API_KEY", raising=False)
            mp.delenv("BRAVE_API_KEY", raising=False)
            mp.delenv("SERPER_API_KEY", raising=False)
            mp.delenv("BING_API_KEY", raising=False)
            mp.delenv("GOOGLE_CSE_API_KEY", raising=False)
            fb = FallbackProvider.from_env()
            assert len(fb._provider_specs) >= 1

    async def test_search_news_failover(self):
        fb = FallbackProvider(providers=[("_test_bad", {}), ("_test_good", {})])
        # _GoodProvider.search_news falls back to search (default impl)
        result = await fb.search_news("news")
        assert result.provider == "good"
