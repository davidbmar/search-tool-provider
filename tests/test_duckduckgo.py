"""Tests for DuckDuckGo provider (mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from search_tool_provider.providers.duckduckgo import DuckDuckGoProvider


@pytest.fixture
def provider():
    return DuckDuckGoProvider()


class TestDuckDuckGo:
    async def test_search(self, provider):
        mock_results = [
            {"title": "Python.org", "href": "https://python.org", "body": "Official site"},
            {"title": "Tutorial", "href": "https://tutorial.com", "body": "Learn Python"},
        ]
        with patch.object(DuckDuckGoProvider, "_sync_search", return_value=mock_results):
            resp = await provider.search("python", max_results=2)

        assert resp.provider == "duckduckgo"
        assert len(resp.results) == 2
        assert resp.results[0].title == "Python.org"
        assert resp.results[0].url == "https://python.org"
        assert resp.results[0].source == "duckduckgo"
        assert resp.results[0].score > 0  # normalized

    async def test_search_news(self, provider):
        mock_results = [
            {"title": "News Item", "url": "https://news.com/1", "body": "Breaking news"},
        ]
        with patch.object(DuckDuckGoProvider, "_sync_news", return_value=mock_results):
            resp = await provider.search_news("tech news")

        assert len(resp.results) == 1
        assert resp.results[0].title == "News Item"

    async def test_get_provider_info(self, provider):
        info = await provider.get_provider_info()
        assert info.name == "duckduckgo"
        assert info.configured is True
        assert "web" in info.features
        assert "news" in info.features

    async def test_search_empty_results(self, provider):
        with patch.object(DuckDuckGoProvider, "_sync_search", return_value=[]):
            resp = await provider.search("obscure query xyz")

        assert resp.results == []

    async def test_search_error_wraps(self, provider):
        from search_tool_provider.exceptions import ProviderUnavailableError

        with patch.object(
            DuckDuckGoProvider, "_sync_search", side_effect=RuntimeError("network error")
        ):
            with pytest.raises(ProviderUnavailableError, match="DuckDuckGo search failed"):
                await provider.search("test")
