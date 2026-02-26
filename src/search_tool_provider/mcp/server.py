"""MCP server exposing search tools to AI agents."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..provider import SearchProvider
from .config import create_provider_from_env

mcp = FastMCP("search-tool-provider")

_provider: SearchProvider | None = None


def _get_provider() -> SearchProvider:
    global _provider
    if _provider is None:
        _provider = create_provider_from_env()
    return _provider


@mcp.tool()
async def search(query: str, max_results: int = 10) -> list[dict]:
    """Search the web.

    Args:
        query: The search query string.
        max_results: Maximum number of results (1-50, default 10).

    Returns:
        List of results with title, url, snippet, score.
    """
    provider = _get_provider()
    resp = await provider.search(query, max_results=max_results)
    return [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "score": r.score,
        }
        for r in resp.results
    ]


@mcp.tool()
async def search_news(query: str, max_results: int = 5) -> list[dict]:
    """Search for recent news articles.

    Args:
        query: The search query string.
        max_results: Maximum number of results (default 5).

    Returns:
        List of news results with title, url, snippet.
    """
    provider = _get_provider()
    resp = await provider.search_news(query, max_results=max_results)
    return [
        {
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
        }
        for r in resp.results
    ]


@mcp.tool()
async def get_answer(query: str) -> dict:
    """Get a direct answer to a question.

    Args:
        query: The question to answer.

    Returns:
        Dict with 'answer' (string or null) and 'provider' name.
    """
    provider = _get_provider()
    answer = await provider.get_answer(query)
    info = await provider.get_provider_info()
    return {"answer": answer, "provider": info.name}


@mcp.tool()
async def get_provider_info() -> dict:
    """Get information about the current search provider.

    Returns:
        Dict with name, configured, api_key_set, features, rate_limit_remaining.
    """
    provider = _get_provider()
    info = await provider.get_provider_info()
    return {
        "name": info.name,
        "configured": info.configured,
        "api_key_set": info.api_key_set,
        "features": info.features,
        "rate_limit_remaining": info.rate_limit_remaining,
    }


def main() -> None:
    mcp.run()
