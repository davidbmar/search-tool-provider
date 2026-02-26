"""Tests for the provider registry."""

import pytest

from search_tool_provider.models import SearchResponse
from search_tool_provider.provider import SearchProvider
from search_tool_provider.registry import _registry, get_provider, register_provider


class _MockProvider(SearchProvider):
    async def search(self, query, max_results=10, **kwargs):
        return SearchResponse(query=query, provider="mock")


class TestRegistry:
    def setup_method(self):
        # Clean up any test registrations
        _registry.pop("test_mock", None)

    def test_register_and_get(self):
        register_provider("test_mock", _MockProvider)
        p = get_provider("test_mock")
        assert isinstance(p, _MockProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent_provider_xyz")

    def test_get_duckduckgo(self):
        p = get_provider("duckduckgo")
        assert type(p).__name__ == "DuckDuckGoProvider"

    def test_get_provider_with_kwargs(self):
        """Verify kwargs are forwarded to the constructor."""
        register_provider("test_mock", _MockProvider)
        p = get_provider("test_mock")
        assert isinstance(p, _MockProvider)

    def teardown_method(self):
        _registry.pop("test_mock", None)
