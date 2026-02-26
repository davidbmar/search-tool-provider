"""Interactive CLI for testing search providers."""

from __future__ import annotations

import asyncio
import os
import sys

from ..models import SearchResponse

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError:
    Console = None  # type: ignore[assignment,misc]


def main() -> None:
    if Console is None:
        print("CLI requires rich. Install with: pip install search-tool-provider[cli]")
        sys.exit(1)
    asyncio.run(_repl())


async def _repl() -> None:
    console = Console()
    from .. import __version__, get_provider
    from ..providers.fallback import FallbackProvider

    console.print(f"\n[bold]search-tool-provider CLI[/bold] (v{__version__})\n")

    # Auto-detect provider
    provider_name = os.environ.get("SEARCH_PROVIDER", "auto")
    provider = _load_provider(console, provider_name)
    if provider is None:
        return

    info = await provider.get_provider_info()
    console.print(f"Provider: [cyan]{info.name}[/cyan]")
    console.print("Type a query, or [bold]/help[/bold] for commands.\n")

    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye!")
            break

        if not query:
            continue

        if query.startswith("/"):
            parts = query.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "/quit" or cmd == "/q":
                console.print("Bye!")
                break
            elif cmd == "/help":
                _show_help(console)
            elif cmd == "/provider":
                if not arg:
                    info = await provider.get_provider_info()
                    console.print(f"Current: [cyan]{info.name}[/cyan]")
                else:
                    new = _load_provider(console, arg)
                    if new:
                        provider = new
                        info = await provider.get_provider_info()
                        console.print(f"Switched to: [cyan]{info.name}[/cyan]")
            elif cmd == "/info":
                await _show_info(console, provider)
            elif cmd == "/answer":
                if not arg:
                    console.print("[red]Usage: /answer <question>[/red]")
                else:
                    await _do_answer(console, provider, arg)
            elif cmd == "/compare":
                if not arg:
                    console.print("[red]Usage: /compare <query>[/red]")
                else:
                    await _do_compare(console, arg)
            elif cmd == "/export":
                _show_export(console)
            else:
                console.print(f"[red]Unknown command: {cmd}[/red]. Try /help")
        else:
            await _do_search(console, provider, query)


def _load_provider(console, name: str):
    from .. import get_provider
    from ..providers.fallback import FallbackProvider

    try:
        if name == "auto":
            return FallbackProvider.from_env()
        return get_provider(name)
    except Exception as exc:
        console.print(f"[red]Failed to load provider {name!r}: {exc}[/red]")
        return None


async def _do_search(console, provider, query: str) -> None:
    try:
        resp = await provider.search(query, max_results=5)
    except Exception as exc:
        console.print(f"[red]Search failed: {exc}[/red]")
        return
    _render_results(console, resp)


async def _do_answer(console, provider, query: str) -> None:
    try:
        answer = await provider.get_answer(query)
    except Exception as exc:
        console.print(f"[red]Answer failed: {exc}[/red]")
        return
    if answer:
        console.print(Panel(answer, title="Answer", border_style="green"))
    else:
        console.print("[dim]No direct answer available from this provider.[/dim]")


async def _do_compare(console, query: str) -> None:
    from ..providers.fallback import FallbackProvider, _ENV_KEYS

    # Build list of available providers
    available: list[tuple[str, object]] = []
    from .. import get_provider

    for name, env_key in _ENV_KEYS:
        if os.environ.get(env_key):
            try:
                available.append((name, get_provider(name)))
            except Exception:
                pass
    try:
        import duckduckgo_search  # noqa: F401
        available.append(("duckduckgo", get_provider("duckduckgo")))
    except (ImportError, Exception):
        pass

    if not available:
        console.print("[red]No providers configured for comparison.[/red]")
        return

    console.print(f"Comparing across: {', '.join(n for n, _ in available)}...")

    async def _search(name, prov):
        try:
            return name, await prov.search(query, max_results=3)
        except Exception as exc:
            return name, exc

    tasks = [_search(n, p) for n, p in available]
    results = await asyncio.gather(*tasks)

    table = Table(title=f"Comparison: {query}")
    table.add_column("Provider", style="cyan")
    table.add_column("#1 Result", style="white")
    table.add_column("Score", style="green")

    for name, result in results:
        if isinstance(result, Exception):
            table.add_row(name, f"[red]Error: {result}[/red]", "-")
        elif result.results:
            r = result.results[0]
            table.add_row(name, f"{r.title}\n{r.url}", f"{r.score:.2f}")
        else:
            table.add_row(name, "[dim]No results[/dim]", "-")

    console.print(table)


async def _show_info(console, provider) -> None:
    info = await provider.get_provider_info()
    table = Table(title="Provider Info")
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Name", info.name)
    table.add_row("Configured", str(info.configured))
    table.add_row("API Key Set", str(info.api_key_set))
    table.add_row("Features", ", ".join(info.features) if info.features else "none")
    if info.rate_limit_remaining is not None:
        table.add_row("Rate Limit Remaining", str(info.rate_limit_remaining))
    console.print(table)


def _show_export(console) -> None:
    lines = ["# Search provider config"]
    env_map = {
        "SEARCH_PROVIDER": os.environ.get("SEARCH_PROVIDER", ""),
        "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY", ""),
        "BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", ""),
        "SERPER_API_KEY": os.environ.get("SERPER_API_KEY", ""),
        "BING_API_KEY": os.environ.get("BING_API_KEY", ""),
        "GOOGLE_CSE_API_KEY": os.environ.get("GOOGLE_CSE_API_KEY", ""),
        "GOOGLE_CSE_CX": os.environ.get("GOOGLE_CSE_CX", ""),
    }
    for key, val in env_map.items():
        if val:
            lines.append(f'{key}="{val}"')
    console.print(Panel("\n".join(lines), title=".env", border_style="blue"))


def _show_help(console) -> None:
    console.print(Panel(
        "[bold]Commands:[/bold]\n"
        "  /provider [name]   Show or switch provider\n"
        "  /compare <query>   Compare results across all configured providers\n"
        "  /answer <query>    Get direct answer\n"
        "  /info              Show provider status and quota\n"
        "  /export            Show .env config for current provider\n"
        "  /help              Show this help\n"
        "  /quit              Exit",
        title="Help",
        border_style="blue",
    ))


def _render_results(console, resp: SearchResponse) -> None:
    if resp.answer:
        console.print(Panel(resp.answer, title="Answer", border_style="green"))

    if not resp.results:
        console.print("[dim]No results found.[/dim]")
        return

    table = Table(title=f"Results ({len(resp.results)})")
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="bold")
    table.add_column("Score", style="green", width=6)
    table.add_column("URL", style="blue")

    for i, r in enumerate(resp.results, 1):
        table.add_row(str(i), r.title, f"{r.score:.2f}", r.url)

    console.print(table)

    if resp.knowledge_graph:
        kg = resp.knowledge_graph
        console.print(Panel(
            f"[bold]{kg.get('title', '')}[/bold]\n{kg.get('description', '')}",
            title="Knowledge Graph",
            border_style="yellow",
        ))
