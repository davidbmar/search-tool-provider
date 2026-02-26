"""Tests for Google CSE provider (mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from search_tool_provider.exceptions import RateLimitError


class TestGoogleCSE:
    def _make(self):
        with patch("search_tool_provider.providers.google_cse.google_build") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            from search_tool_provider.providers.google_cse import GoogleCSEProvider
            provider = GoogleCSEProvider(api_key="test-key", cx="test-cx")
            return provider, mock_service

    async def test_search(self):
        provider, mock_service = self._make()
        mock_service.cse.return_value.list.return_value.execute.return_value = {
            "items": [
                {"title": "Google Result", "link": "http://g.com", "snippet": "text"},
            ],
            "searchInformation": {"totalResults": "5000"},
        }
        result = await provider.search("test")

        assert result.provider == "google_cse"
        assert len(result.results) == 1
        assert result.total_results == 5000

    async def test_search_empty(self):
        provider, mock_service = self._make()
        mock_service.cse.return_value.list.return_value.execute.return_value = {
            "searchInformation": {"totalResults": "0"},
        }
        result = await provider.search("nonexistent")
        assert result.results == []

    async def test_provider_info(self):
        provider, _ = self._make()
        info = await provider.get_provider_info()
        assert info.name == "google_cse"
        assert info.api_key_set is True
