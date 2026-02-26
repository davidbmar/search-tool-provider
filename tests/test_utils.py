"""Tests for utility functions."""

import asyncio

import pytest

from search_tool_provider.models import SearchResult
from search_tool_provider.utils import TTLCache, clean_html, deduplicate_results, normalize_scores


class TestNormalizeScores:
    def test_all_zero_gets_position_based(self):
        results = [
            SearchResult("A", "http://a.com"),
            SearchResult("B", "http://b.com"),
            SearchResult("C", "http://c.com"),
        ]
        normalize_scores(results)
        assert results[0].score > results[1].score > results[2].score
        # Formula: 1.0 - (i / (n + 1)), so first = 1.0 - 0/4 = 1.0
        assert results[0].score == pytest.approx(1.0, abs=0.01)

    def test_already_normalized(self):
        results = [
            SearchResult("A", "http://a.com", score=0.9),
            SearchResult("B", "http://b.com", score=0.5),
        ]
        normalize_scores(results)
        assert results[0].score == 0.9
        assert results[1].score == 0.5

    def test_scale_to_range(self):
        results = [
            SearchResult("A", "http://a.com", score=100),
            SearchResult("B", "http://b.com", score=50),
            SearchResult("C", "http://c.com", score=0),
        ]
        normalize_scores(results)
        assert results[0].score == 1.0
        assert results[1].score == 0.5
        assert results[2].score == 0.0

    def test_empty_list(self):
        assert normalize_scores([]) == []

    def test_single_nonzero(self):
        results = [SearchResult("A", "http://a.com", score=5.0)]
        normalize_scores(results)
        assert results[0].score == 1.0


class TestDeduplicateResults:
    def test_removes_duplicates(self):
        results = [
            SearchResult("A", "http://a.com/"),
            SearchResult("A copy", "http://a.com"),
            SearchResult("B", "http://b.com"),
        ]
        deduped = deduplicate_results(results)
        assert len(deduped) == 2
        assert deduped[0].title == "A"
        assert deduped[1].title == "B"

    def test_preserves_order(self):
        results = [
            SearchResult("C", "http://c.com"),
            SearchResult("A", "http://a.com"),
            SearchResult("B", "http://b.com"),
        ]
        deduped = deduplicate_results(results)
        assert [r.title for r in deduped] == ["C", "A", "B"]

    def test_empty(self):
        assert deduplicate_results([]) == []


class TestCleanHtml:
    def test_strips_tags(self):
        assert clean_html("<b>bold</b> text") == "bold text"

    def test_collapses_whitespace(self):
        assert clean_html("hello   world") == "hello world"

    def test_empty_string(self):
        assert clean_html("") == ""

    def test_nested_tags(self):
        assert clean_html("<div><p>inner</p></div>") == "inner"


class TestTTLCache:
    async def test_set_and_get(self):
        cache = TTLCache(ttl=10)
        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

    async def test_expired_entry(self):
        cache = TTLCache(ttl=0)  # Expire immediately
        await cache.set("key1", "value1")
        # ttl=0 means anything is expired
        assert await cache.get("key1") is None

    async def test_missing_key(self):
        cache = TTLCache()
        assert await cache.get("nonexistent") is None

    async def test_clear(self):
        cache = TTLCache()
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.clear()
        assert await cache.get("a") is None

    async def test_max_size_eviction(self):
        cache = TTLCache(ttl=60, max_size=2)
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)  # Should evict oldest
        assert await cache.get("c") == 3
        # One of a or b should have been evicted
        values = [await cache.get("a"), await cache.get("b")]
        assert None in values

    def test_make_key_deterministic(self):
        k1 = TTLCache._make_key("query", 10)
        k2 = TTLCache._make_key("query", 10)
        k3 = TTLCache._make_key("query", 5)
        assert k1 == k2
        assert k1 != k3
