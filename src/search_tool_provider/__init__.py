"""search-tool-provider — Unified async web search across multiple backends."""

__version__ = "0.1.0"

from .exceptions import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    SearchProviderError,
    SearchTimeoutError,
)
from .models import ProviderInfo, SearchQuery, SearchResponse, SearchResult, SearchType, TimeRange
from .provider import SearchProvider
from .registry import get_provider, register_provider

__all__ = [
    # Core
    "SearchProvider",
    "get_provider",
    "register_provider",
    # Models
    "SearchQuery",
    "SearchResult",
    "SearchResponse",
    "ProviderInfo",
    "SearchType",
    "TimeRange",
    # Exceptions
    "SearchProviderError",
    "AuthenticationError",
    "RateLimitError",
    "SearchTimeoutError",
    "ProviderUnavailableError",
    # Version
    "__version__",
]
