"""Tests for HTTP-based providers (Tavily, Brave, Serper, Bing) — all mocked."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from search_tool_provider.exceptions import (
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    SearchTimeoutError,
)


def _mock_response(status_code=200, json_data=None, headers=None):
    resp = AsyncMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    resp.text = "error body"
    return resp


# ── Tavily ──────────────────────────────────────────────────────────

class TestTavily:
    def _make(self):
        from search_tool_provider.providers.tavily import TavilyProvider
        return TavilyProvider(api_key="test-key")

    async def test_search(self):
        provider = self._make()
        mock_data = {
            "results": [
                {"title": "Result 1", "url": "http://r1.com", "content": "snippet 1", "score": 0.9},
                {"title": "Result 2", "url": "http://r2.com", "content": "snippet 2", "score": 0.7},
            ],
            "answer": None,
        }
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            result = await provider.search("test query")

        assert result.provider == "tavily"
        assert len(result.results) == 2
        assert result.results[0].score == 0.9
        assert result.results[0].source == "tavily"

    async def test_search_with_answer(self):
        provider = self._make()
        mock_data = {
            "results": [{"title": "R", "url": "http://r.com", "content": "s", "score": 0.8}],
            "answer": "The answer is 42",
        }
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            result = await provider.search("meaning of life", include_answer=True)

        assert result.answer == "The answer is 42"

    async def test_get_answer(self):
        provider = self._make()
        mock_data = {"results": [], "answer": "Paris"}
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            answer = await provider.get_answer("capital of France")

        assert answer == "Paris"

    async def test_auth_error(self):
        provider = self._make()
        resp = _mock_response(status_code=401)
        with patch("httpx.AsyncClient.post", return_value=resp):
            with pytest.raises(AuthenticationError):
                await provider.search("test")

    async def test_rate_limit(self):
        provider = self._make()
        resp = _mock_response(status_code=429)
        with patch("httpx.AsyncClient.post", return_value=resp):
            with pytest.raises(RateLimitError):
                await provider.search("test")

    async def test_timeout(self):
        provider = self._make()
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(SearchTimeoutError):
                await provider.search("test")

    def test_missing_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AuthenticationError):
                from search_tool_provider.providers.tavily import TavilyProvider
                TavilyProvider()

    async def test_provider_info(self):
        provider = self._make()
        info = await provider.get_provider_info()
        assert info.name == "tavily"
        assert info.api_key_set is True
        assert "answer" in info.features


# ── Brave ───────────────────────────────────────────────────────────

class TestBrave:
    def _make(self):
        from search_tool_provider.providers.brave import BraveProvider
        return BraveProvider(api_key="test-key")

    async def test_search(self):
        provider = self._make()
        mock_data = {
            "web": {
                "results": [
                    {"title": "Brave Result", "url": "http://b.com", "description": "desc"},
                ]
            },
        }
        resp = _mock_response(json_data=mock_data, headers={"x-ratelimit-remaining": "950"})
        with patch("httpx.AsyncClient.get", return_value=resp):
            result = await provider.search("test")

        assert result.provider == "brave"
        assert len(result.results) == 1
        assert result.results[0].source == "brave"

    async def test_infobox_mapped_to_knowledge_graph(self):
        provider = self._make()
        mock_data = {
            "web": {"results": []},
            "infobox": {
                "title": "Python",
                "description": "A programming language",
                "facts": [{"label": "Designer", "value": "Guido van Rossum"}],
            },
        }
        resp = _mock_response(json_data=mock_data, headers={})
        with patch("httpx.AsyncClient.get", return_value=resp):
            result = await provider.search("python")

        assert result.knowledge_graph is not None
        assert result.knowledge_graph["title"] == "Python"

    async def test_search_news(self):
        provider = self._make()
        mock_data = {
            "results": [
                {"title": "News", "url": "http://news.com", "description": "Breaking"},
            ]
        }
        resp = _mock_response(json_data=mock_data, headers={})
        with patch("httpx.AsyncClient.get", return_value=resp):
            result = await provider.search_news("tech")

        assert len(result.results) == 1

    async def test_rate_limit_remaining_tracked(self):
        provider = self._make()
        mock_data = {"web": {"results": []}}
        resp = _mock_response(json_data=mock_data, headers={"x-ratelimit-remaining": "42"})
        with patch("httpx.AsyncClient.get", return_value=resp):
            await provider.search("test")

        info = await provider.get_provider_info()
        assert info.rate_limit_remaining == 42

    async def test_auth_error(self):
        provider = self._make()
        resp = _mock_response(status_code=401)
        with patch("httpx.AsyncClient.get", return_value=resp):
            with pytest.raises(AuthenticationError):
                await provider.search("test")


# ── Serper ──────────────────────────────────────────────────────────

class TestSerper:
    def _make(self):
        from search_tool_provider.providers.serper import SerperProvider
        return SerperProvider(api_key="test-key")

    async def test_search(self):
        provider = self._make()
        mock_data = {
            "organic": [
                {"title": "Google Result", "link": "http://g.com", "snippet": "text"},
            ],
        }
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            result = await provider.search("test")

        assert result.provider == "serper"
        assert result.results[0].url == "http://g.com"

    async def test_answer_box(self):
        provider = self._make()
        mock_data = {
            "organic": [],
            "answerBox": {"answer": "42", "snippet": "The answer is 42"},
        }
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            result = await provider.search("meaning of life")

        assert result.answer == "42"

    async def test_knowledge_graph(self):
        provider = self._make()
        mock_data = {
            "organic": [],
            "knowledgeGraph": {
                "title": "Python",
                "type": "Programming Language",
                "description": "A high-level language",
                "attributes": {"designer": "Guido"},
            },
        }
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            result = await provider.search("python lang")

        assert result.knowledge_graph["title"] == "Python"
        assert result.knowledge_graph["type"] == "Programming Language"

    async def test_get_answer_from_answer_box(self):
        provider = self._make()
        mock_data = {"organic": [], "answerBox": {"answer": "Paris"}}
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            answer = await provider.get_answer("capital of France")

        assert answer == "Paris"

    async def test_get_answer_from_knowledge_graph(self):
        provider = self._make()
        mock_data = {
            "organic": [],
            "knowledgeGraph": {"description": "The capital is Paris"},
        }
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            answer = await provider.get_answer("capital of France")

        assert answer == "The capital is Paris"

    async def test_get_answer_list_type(self):
        provider = self._make()
        mock_data = {
            "organic": [],
            "answerBox": {"list": ["Step 1", "Step 2", "Step 3"]},
        }
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            answer = await provider.get_answer("how to")

        assert "Step 1" in answer
        assert "Step 2" in answer

    async def test_search_news(self):
        provider = self._make()
        mock_data = {
            "news": [{"title": "Breaking", "link": "http://n.com", "snippet": "News item"}],
        }
        resp = _mock_response(json_data=mock_data)
        with patch("httpx.AsyncClient.post", return_value=resp):
            result = await provider.search_news("tech")

        assert len(result.results) == 1

    async def test_provider_info(self):
        provider = self._make()
        info = await provider.get_provider_info()
        assert "knowledge_graph" in info.features


# ── Bing ────────────────────────────────────────────────────────────

class TestBing:
    def _make(self):
        from search_tool_provider.providers.bing import BingProvider
        return BingProvider(api_key="test-key")

    async def test_search(self):
        provider = self._make()
        mock_data = {
            "webPages": {
                "value": [
                    {"name": "Bing Result", "url": "http://bing.com/r", "snippet": "text"},
                ],
                "totalEstimatedMatches": 1000,
            },
        }
        resp = _mock_response(json_data=mock_data, headers={})
        with patch("httpx.AsyncClient.get", return_value=resp):
            result = await provider.search("test")

        assert result.provider == "bing"
        assert result.results[0].title == "Bing Result"
        assert result.total_results == 1000

    async def test_search_news(self):
        provider = self._make()
        mock_data = {
            "value": [
                {"name": "News", "url": "http://news.com", "description": "Breaking"},
            ]
        }
        resp = _mock_response(json_data=mock_data, headers={})
        with patch("httpx.AsyncClient.get", return_value=resp):
            result = await provider.search_news("tech")

        assert len(result.results) == 1

    async def test_rate_limit_with_retry_after(self):
        provider = self._make()
        resp = _mock_response(status_code=429, headers={"Retry-After": "60"})
        with patch("httpx.AsyncClient.get", return_value=resp):
            with pytest.raises(RateLimitError) as exc_info:
                await provider.search("test")

        assert exc_info.value.retry_after == 60.0

    async def test_timeout(self):
        provider = self._make()
        with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(SearchTimeoutError):
                await provider.search("test")
