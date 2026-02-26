"""Tests for the public API surface."""

import search_tool_provider


class TestPublicAPI:
    def test_version(self):
        assert search_tool_provider.__version__ == "0.1.0"

    def test_all_exports_accessible(self):
        """Every name in __all__ should be importable."""
        for name in search_tool_provider.__all__:
            assert hasattr(search_tool_provider, name), f"{name} not found in package"

    def test_core_classes(self):
        assert search_tool_provider.SearchProvider is not None
        assert search_tool_provider.SearchResult is not None
        assert search_tool_provider.SearchResponse is not None
        assert search_tool_provider.SearchQuery is not None
        assert search_tool_provider.ProviderInfo is not None

    def test_registry_functions(self):
        assert callable(search_tool_provider.get_provider)
        assert callable(search_tool_provider.register_provider)

    def test_exceptions(self):
        assert issubclass(search_tool_provider.AuthenticationError, search_tool_provider.SearchProviderError)
        assert issubclass(search_tool_provider.RateLimitError, search_tool_provider.SearchProviderError)
        assert issubclass(search_tool_provider.SearchTimeoutError, search_tool_provider.SearchProviderError)
        assert issubclass(search_tool_provider.ProviderUnavailableError, search_tool_provider.SearchProviderError)

    def test_enums(self):
        assert search_tool_provider.SearchType.WEB.value == "web"
        assert search_tool_provider.TimeRange.WEEK.value == "week"
