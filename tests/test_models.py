"""Tests for data models."""

import pytest

from search_tool_provider.models import (
    ProviderInfo,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchType,
    TimeRange,
)


class TestSearchQuery:
    def test_defaults(self):
        q = SearchQuery("python tutorial")
        assert q.query == "python tutorial"
        assert q.max_results == 10
        assert q.search_type == SearchType.WEB
        assert q.safe_search is True

    def test_custom_values(self):
        q = SearchQuery(
            "news",
            max_results=5,
            search_type=SearchType.NEWS,
            language="en",
            region="us",
            time_range=TimeRange.WEEK,
            include_answer=True,
        )
        assert q.max_results == 5
        assert q.time_range == TimeRange.WEEK
        assert q.include_answer is True

    def test_empty_query_raises(self):
        with pytest.raises(ValueError, match="query must not be empty"):
            SearchQuery("")

    def test_whitespace_query_raises(self):
        with pytest.raises(ValueError, match="query must not be empty"):
            SearchQuery("   ")

    def test_max_results_too_low(self):
        with pytest.raises(ValueError, match="max_results must be between"):
            SearchQuery("test", max_results=0)

    def test_max_results_too_high(self):
        with pytest.raises(ValueError, match="max_results must be between"):
            SearchQuery("test", max_results=51)


class TestSearchResult:
    def test_defaults(self):
        r = SearchResult(title="Test", url="https://example.com")
        assert r.snippet == ""
        assert r.score == 0.0
        assert r.raw == {}

    def test_repr(self):
        r = SearchResult(title="Test", url="https://example.com", score=0.95)
        assert "0.95" in repr(r)
        assert "Test" in repr(r)


class TestSearchResponse:
    def test_empty(self):
        resp = SearchResponse()
        assert resp.results == []
        assert resp.answer is None

    def test_with_results(self):
        results = [SearchResult("A", "http://a.com"), SearchResult("B", "http://b.com")]
        resp = SearchResponse(results=results, query="test", provider="mock")
        assert len(resp.results) == 2
        assert resp.provider == "mock"

    def test_repr(self):
        resp = SearchResponse(provider="tavily", answer="42")
        assert "tavily" in repr(resp)
        assert "yes" in repr(resp)


class TestProviderInfo:
    def test_defaults(self):
        info = ProviderInfo(name="test")
        assert info.configured is False
        assert info.features == []
        assert info.rate_limit_remaining is None


class TestEnums:
    def test_search_type_values(self):
        assert SearchType.WEB.value == "web"
        assert SearchType.NEWS.value == "news"
        assert SearchType.IMAGES.value == "images"

    def test_time_range_values(self):
        assert TimeRange.DAY.value == "day"
        assert TimeRange.YEAR.value == "year"
