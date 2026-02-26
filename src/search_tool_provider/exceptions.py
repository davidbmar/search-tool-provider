"""Exception hierarchy for search providers."""

from __future__ import annotations


class SearchProviderError(Exception):
    """Base exception for all search provider errors."""


class AuthenticationError(SearchProviderError):
    """Bad or missing API key."""


class RateLimitError(SearchProviderError):
    """API quota exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying, if known.
    """

    def __init__(self, message: str = "Rate limit exceeded", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class SearchTimeoutError(SearchProviderError):
    """Provider did not respond in time."""


class ProviderUnavailableError(SearchProviderError):
    """Backend is down or unreachable."""
