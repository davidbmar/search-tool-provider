"""Data models for search queries, results, and provider info."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SearchType(Enum):
    """Type of search to perform."""

    WEB = "web"
    NEWS = "news"
    IMAGES = "images"


class TimeRange(Enum):
    """Time range filter for search results."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


@dataclass
class SearchQuery:
    """A search query with optional filters.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (1–50).
        search_type: Type of search (web, news, images).
        language: Language code (e.g. "en", "es").
        region: Region code (e.g. "us", "gb").
        time_range: Filter results by recency.
        include_answer: Request a direct answer if the provider supports it.
        safe_search: Enable safe search filtering.
    """

    query: str
    max_results: int = 10
    search_type: SearchType = SearchType.WEB
    language: str | None = None
    region: str | None = None
    time_range: TimeRange | None = None
    include_answer: bool = False
    safe_search: bool = True

    def __post_init__(self) -> None:
        if not self.query or not self.query.strip():
            raise ValueError("query must not be empty")
        if self.max_results < 1 or self.max_results > 50:
            raise ValueError("max_results must be between 1 and 50")


@dataclass
class SearchResult:
    """A single search result.

    Attributes:
        title: Page title.
        url: Result URL.
        snippet: Text snippet / description.
        source: Provider that returned this result (e.g. "tavily").
        score: Relevance score normalized to 0.0–1.0.
        published_date: Publication date if available.
        raw: Raw provider-specific data.
    """

    title: str
    url: str
    snippet: str = ""
    source: str = ""
    score: float = 0.0
    published_date: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"SearchResult(title={self.title!r}, url={self.url!r}, score={self.score:.2f})"


@dataclass
class SearchResponse:
    """Container for search results plus metadata.

    Attributes:
        results: List of search results.
        query: The original query string.
        provider: Name of the provider that answered.
        answer: Direct answer string if the provider supports it.
        knowledge_graph: Structured data (knowledge graph / infobox).
        total_results: Estimated total results from the provider.
    """

    results: list[SearchResult] = field(default_factory=list)
    query: str = ""
    provider: str = ""
    answer: str | None = None
    knowledge_graph: dict[str, Any] | None = None
    total_results: int | None = None

    def __repr__(self) -> str:
        return (
            f"SearchResponse(provider={self.provider!r}, "
            f"results={len(self.results)}, answer={'yes' if self.answer else 'no'})"
        )


@dataclass
class ProviderInfo:
    """Status information for a search provider.

    Attributes:
        name: Provider name (e.g. "tavily").
        configured: Whether the provider has valid credentials.
        api_key_set: Whether an API key is present (doesn't validate it).
        features: List of supported features (e.g. ["answer", "news"]).
        rate_limit_remaining: Remaining API calls if known.
    """

    name: str
    configured: bool = False
    api_key_set: bool = False
    features: list[str] = field(default_factory=list)
    rate_limit_remaining: int | None = None
