"""Tests for admin API endpoints — test-connection and save-config."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from search_tool_provider.admin.app import app

# Use httpx async test client (available via anyio/httpx already in deps)
from httpx import ASGITransport, AsyncClient


def _mock_response(status_code=200, json_data=None, headers=None):
    """Match the mock pattern used in test_http_providers.py."""
    resp = AsyncMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    resp.text = "error body"
    return resp


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestTestConnection:
    async def test_serper_success(self, client):
        """Serper test-connection returns success when search works."""
        from search_tool_provider.models import SearchResponse, SearchResult

        mock_result = SearchResponse(
            results=[SearchResult(title="Test", url="http://example.com", snippet="text")],
            query="test",
            provider="serper",
        )

        with patch(
            "search_tool_provider.providers.serper.SerperProvider.search",
            return_value=mock_result,
        ):
            resp = await client.post(
                "/api/test-connection",
                json={"provider": "serper", "api_key": "fake-key"},
            )

        data = resp.json()
        assert data["success"] is True
        assert data["provider"] == "serper"
        assert data["results"] >= 1

    async def test_brave_success(self, client):
        """Brave test-connection returns success when search works."""
        from search_tool_provider.models import SearchResponse, SearchResult

        mock_result = SearchResponse(
            results=[SearchResult(title="Test", url="http://example.com", snippet="text")],
            query="test",
            provider="brave",
        )

        with patch(
            "search_tool_provider.providers.brave.BraveProvider.search",
            return_value=mock_result,
        ):
            resp = await client.post(
                "/api/test-connection",
                json={"provider": "brave", "api_key": "fake-key"},
            )

        data = resp.json()
        assert data["success"] is True
        assert data["provider"] == "brave"

    async def test_bad_provider_returns_error(self, client):
        """Unknown provider returns error, not a crash."""
        resp = await client.post(
            "/api/test-connection",
            json={"provider": "nonexistent", "api_key": "x"},
        )
        data = resp.json()
        assert data["success"] is False
        assert "error" in data


class TestHealthCheck:
    async def test_fresh_dashboard_shows_configured_providers(self, client):
        """Health-check reflects env vars — a fresh dashboard load shows configured providers."""
        import os

        # Set keys as if .env was loaded
        os.environ["SERPER_API_KEY"] = "fake-serper"
        os.environ["BRAVE_API_KEY"] = "fake-brave"

        from search_tool_provider.models import SearchResponse, SearchResult

        mock_result = SearchResponse(
            results=[SearchResult(title="T", url="http://x.com", snippet="s")],
            query="test",
            provider="mock",
        )

        try:
            with patch(
                "search_tool_provider.providers.serper.SerperProvider.search",
                return_value=mock_result,
            ), patch(
                "search_tool_provider.providers.brave.BraveProvider.search",
                return_value=mock_result,
            ):
                resp = await client.get("/api/health-check")

            data = resp.json()
            names = [p["provider"] for p in data["providers"]]
            assert "serper" in names, f"serper missing from {names}"
            assert "brave" in names, f"brave missing from {names}"

            # Verify no-cache header
            assert resp.headers.get("cache-control") == "no-store"
        finally:
            os.environ.pop("SERPER_API_KEY", None)
            os.environ.pop("BRAVE_API_KEY", None)


class TestSaveConfig:
    async def test_save_creates_env(self, client, tmp_path):
        """POST /api/save-config merges into .env and sets os.environ."""
        import os

        env_path = tmp_path / ".env"

        with patch(
            "search_tool_provider.admin.app._env_path", env_path
        ):
            resp = await client.post(
                "/api/save-config",
                json={"provider": "serper", "api_key": "sk-test-123"},
            )

        data = resp.json()
        assert data["success"] is True
        assert "SEARCH_PROVIDER" in data["keys"]
        assert "SERPER_API_KEY" in data["keys"]
        # No path disclosure in response
        assert "path" not in data

        # Verify os.environ was updated
        assert os.environ.get("SEARCH_PROVIDER") == "serper"
        assert os.environ.get("SERPER_API_KEY") == "sk-test-123"

        # Verify file was written
        assert env_path.exists()
        content = env_path.read_text()
        assert "SEARCH_PROVIDER=serper" in content
        assert "SERPER_API_KEY=sk-test-123" in content

        # Clean up env
        os.environ.pop("SEARCH_PROVIDER", None)
        os.environ.pop("SERPER_API_KEY", None)
