"""Admin UI with teaching setup wizard and search playground."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..provider import SearchProvider

_DIR = Path(__file__).parent
app = FastAPI(title="search-tool-provider admin")
app.mount("/static", StaticFiles(directory=_DIR / "static"), name="static")
templates = Jinja2Templates(directory=_DIR / "templates")

_provider: SearchProvider | None = None
_provider_name: str = ""


# ── Models ──────────────────────────────────────────────────────

class ConnectionRequest(BaseModel):
    provider: str
    api_key: str = ""
    cx: str = ""


# ── Page routes ─────────────────────────────────────────────────

@app.get("/")
async def index():
    return RedirectResponse("/setup")


@app.get("/setup")
async def setup_page(request: Request):
    return templates.TemplateResponse("setup.html", {"request": request, "active": "setup"})


@app.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "active": "dashboard"})


@app.get("/config")
async def config_page(request: Request):
    return templates.TemplateResponse("config.html", {"request": request, "active": "config"})


# ── API routes ──────────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    global _provider
    if _provider is None:
        # Try auto-loading
        try:
            _load_from_env()
        except Exception:
            return {
                "configured": False,
                "provider": "none",
                "features": [],
                "rate_limit_remaining": None,
                "env_vars": _get_env_status(),
            }

    info = await _provider.get_provider_info()
    return {
        "configured": info.configured,
        "provider": info.name,
        "features": info.features,
        "rate_limit_remaining": info.rate_limit_remaining,
        "env_vars": _get_env_status(),
    }


@app.post("/api/test-connection")
async def api_test_connection(req: ConnectionRequest):
    global _provider, _provider_name
    try:
        provider = _create_provider(req.provider, req.api_key, req.cx)
        # Quick test search
        resp = await provider.search("test", max_results=1)
        _provider = provider
        _provider_name = req.provider
        return {"success": True, "provider": req.provider, "results": len(resp.results)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.get("/api/search")
async def api_search(q: str, max_results: int = 10):
    provider = _require_provider()
    if isinstance(provider, dict):
        return provider
    resp = await provider.search(q, max_results=max_results)
    return {
        "results": [
            {"title": r.title, "url": r.url, "snippet": r.snippet, "score": r.score}
            for r in resp.results
        ],
        "answer": resp.answer,
        "provider": resp.provider,
    }


@app.get("/api/compare")
async def api_compare(q: str):
    from ..providers.fallback import _ENV_KEYS
    from ..registry import get_provider

    providers_to_test: list[tuple[str, SearchProvider]] = []

    for name, env_key in _ENV_KEYS:
        if os.environ.get(env_key):
            try:
                providers_to_test.append((name, get_provider(name)))
            except Exception:
                pass

    try:
        import duckduckgo_search  # noqa: F401
        providers_to_test.append(("duckduckgo", get_provider("duckduckgo")))
    except (ImportError, Exception):
        pass

    if _provider and not any(n == _provider_name for n, _ in providers_to_test):
        providers_to_test.append((_provider_name, _provider))

    async def _search_one(name: str, prov: SearchProvider):
        try:
            resp = await prov.search(q, max_results=3)
            return {
                "provider": name,
                "results": [
                    {"title": r.title, "url": r.url, "snippet": r.snippet, "score": r.score}
                    for r in resp.results
                ],
            }
        except Exception as exc:
            return {"provider": name, "error": str(exc), "results": []}

    comparisons = await asyncio.gather(*[_search_one(n, p) for n, p in providers_to_test])
    return {"comparisons": list(comparisons)}


# ── Helpers ─────────────────────────────────────────────────────

def _create_provider(name: str, api_key: str = "", cx: str = "") -> SearchProvider:
    from ..registry import get_provider
    from ..providers.fallback import FallbackProvider

    if name == "fallback":
        return FallbackProvider.from_env()
    elif name == "duckduckgo":
        return get_provider("duckduckgo")
    elif name == "google_cse":
        return get_provider("google_cse", api_key=api_key, cx=cx)
    else:
        return get_provider(name, api_key=api_key)


def _load_from_env() -> None:
    global _provider, _provider_name
    from ..mcp.config import create_provider_from_env
    _provider = create_provider_from_env()
    info_coro = _provider.get_provider_info()
    # We're in an async context, but this is called from a sync path
    # The provider is loaded — name will be set on first status call
    _provider_name = "auto"


def _require_provider():
    global _provider
    if _provider is None:
        try:
            _load_from_env()
        except Exception:
            pass
    if _provider is None:
        return {"error": "No provider configured. Run setup first."}
    return _provider


def _get_env_status() -> dict:
    return {
        "TAVILY_API_KEY": bool(os.environ.get("TAVILY_API_KEY")),
        "BRAVE_API_KEY": bool(os.environ.get("BRAVE_API_KEY")),
        "SERPER_API_KEY": bool(os.environ.get("SERPER_API_KEY")),
        "BING_API_KEY": bool(os.environ.get("BING_API_KEY")),
        "GOOGLE_CSE_API_KEY": bool(os.environ.get("GOOGLE_CSE_API_KEY")),
        "GOOGLE_CSE_CX": bool(os.environ.get("GOOGLE_CSE_CX")),
    }


def main() -> None:
    import uvicorn

    port = int(os.environ.get("SEARCH_PROVIDER_ADMIN_PORT", "8200"))
    uvicorn.run(app, host="0.0.0.0", port=port)
