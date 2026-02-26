"""Provider registry with lazy imports."""

from __future__ import annotations

from typing import Any, Callable

from .provider import SearchProvider

_registry: dict[str, Callable[..., SearchProvider]] = {}

# Maps provider name → (module path, class name, extras hint)
_BUILTINS: dict[str, tuple[str, str, str]] = {
    "duckduckgo": (
        "search_tool_provider.providers.duckduckgo",
        "DuckDuckGoProvider",
        "pip install search-tool-provider[duckduckgo]",
    ),
    "tavily": (
        "search_tool_provider.providers.tavily",
        "TavilyProvider",
        "pip install search-tool-provider[tavily]",
    ),
    "brave": (
        "search_tool_provider.providers.brave",
        "BraveProvider",
        "pip install search-tool-provider[brave]",
    ),
    "serper": (
        "search_tool_provider.providers.serper",
        "SerperProvider",
        "pip install search-tool-provider[serper]",
    ),
    "google_cse": (
        "search_tool_provider.providers.google_cse",
        "GoogleCSEProvider",
        "pip install search-tool-provider[google]",
    ),
    "bing": (
        "search_tool_provider.providers.bing",
        "BingProvider",
        "pip install search-tool-provider[bing]",
    ),
    "fallback": (
        "search_tool_provider.providers.fallback",
        "FallbackProvider",
        "pip install search-tool-provider",
    ),
}


def register_provider(name: str, factory: Callable[..., SearchProvider]) -> None:
    """Register a provider factory.

    Args:
        name: Provider name (e.g. "my_custom_search").
        factory: Callable that returns a SearchProvider instance.
    """
    _registry[name] = factory


def get_provider(name: str, **kwargs: Any) -> SearchProvider:
    """Get a provider instance by name.

    Lazily imports built-in providers on first use.

    Args:
        name: Provider name (e.g. "tavily", "duckduckgo").
        **kwargs: Passed to the provider constructor.

    Returns:
        SearchProvider instance.

    Raises:
        ValueError: Unknown provider name.
        ImportError: Missing optional dependency.
    """
    if name not in _registry:
        _try_register_builtin(name)
    if name not in _registry:
        available = sorted(set(list(_registry.keys()) + list(_BUILTINS.keys())))
        raise ValueError(f"Unknown provider {name!r}. Available: {', '.join(available)}")
    return _registry[name](**kwargs)


def _try_register_builtin(name: str) -> None:
    """Attempt to import and register a built-in provider."""
    if name not in _BUILTINS:
        return
    module_path, class_name, install_hint = _BUILTINS[name]
    try:
        import importlib

        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        _registry[name] = cls
    except ImportError as exc:
        raise ImportError(
            f"Provider {name!r} requires additional dependencies. "
            f"Install with: {install_hint}"
        ) from exc
