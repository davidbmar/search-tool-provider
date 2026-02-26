"""Environment-based provider configuration for the MCP server."""

from __future__ import annotations

import os

from ..provider import SearchProvider


def create_provider_from_env() -> SearchProvider:
    """Create a search provider from environment variables.

    If SEARCH_PROVIDER is set, uses that specific provider.
    Otherwise, auto-builds a fallback chain from available API keys.

    Returns:
        Configured SearchProvider instance.

    Raises:
        ValueError: If SEARCH_PROVIDER is set to an unknown value.
        SearchProviderError: If no providers can be configured.
    """
    name = os.environ.get("SEARCH_PROVIDER", "").strip()

    if name == "auto" or name == "fallback" or not name:
        from ..providers.fallback import FallbackProvider

        return FallbackProvider.from_env()

    from ..registry import get_provider

    return get_provider(name)
