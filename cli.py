"""Axon Bridge CLI — manage and interact with the Axon token-optimization server.

Commands
--------
axon serve          Start the Axon server
axon benchmark      Benchmark all strategies against a JSON payload file
axon encode         Compress a JSON string and print the result
axon session show   Print the event history for a session
axon session clear  Delete a session from the store
axon pricing        Show current model pricing table
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="axon",
    help="Axon Token Bridge — LLM token-optimization middleware.",
    no_args_is_help=True,
)
session_app = typer.Typer(help="Manage Axon sessions.")
app.add_typer(session_app, name="session")

console = Console()


# ── serve ─────────────────────────────────────────────────────────────────────

@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", envvar="AXON_HOST", help="Bind host"),
    port: int = typer.Option(8080, envvar="AXON_PORT", help="Bind port"),
    reload: bool = typer.Option(False, help="Enable hot-reload (dev only)"),
    workers: int = typer.Option(1, help="Number of uvicorn workers"),
    log_level: str = typer.Option("info", help="Log level"),
) -> None:
    """Start the Axon Bridge server."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is required. Run: pip install uvicorn[/red]")
        raise typer.Exit(1)

    console.print(f"[bold green]Starting Axon Bridge[/bold green] on {host}:{port}")
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level=log_level,
    )


# ── benchmark ─────────────────────────────────────────────────────────────────

@app.command()
def benchmark(
    payload_file: Path = typer.Argument(..., help="Path to a JSON file to benchmark"),
    model: Optional[str] = typer.Option(None, help="Target model for token counting"),
    session_id: Optional[str] = typer.Option(None, help="Session ID for multi-turn strategies"),
) -> None:
    """Benchmark all encoding strategies against a JSON payload file."""
    if not payload_file.exists():
        console.print(f"[red]File not found: {payload_file}[/red]")
        raise typer.Exit(1)

    try:
        obj = json.loads(payload_file.read_text())
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid JSON: {exc}[/red]")
        raise typer.Exit(1)

    sys.path.insert(0, str(Path(__file__).parent))
    from services.token_optimizer import TokenOptimizer

    optimizer = TokenOptimizer()
    result = optimizer.optimize(obj, session_id=session_id, model=model)

    table = Table(title=f"Strategy Benchmark — {payload_file.name}", show_lines=True)
    table.add_column("Strategy", style="cyan")
    table.add_column("Tokens", justify="right")
    table.add_column("Savings %", justify="right")
    table.add_column("Winner", justify="center")

    for r in sorted(result.all_results, key=lambda x: x.token_estimate):
        is_winner = r.strategy == result.winner.strategy
        table.add_row(
            r.strategy,
            str(r.token_estimate),
            f"{r.savings_vs_json_pct:+.1f}%",
            "✅" if is_winner else "",
            style="bold green" if is_winner else None,
        )

    console.print(table)
    console.print(
        f"\n[bold]Winner:[/bold] [green]{result.winner.strategy}[/green] "
        f"({result.winner.token_estimate} tokens, "
        f"[green]{result.winner.savings_vs_json_pct:+.1f}%[/green] vs JSON)\n"
    )


# ── encode ────────────────────────────────────────────────────────────────────

@app.command()
def encode(
    payload: str = typer.Argument(..., help="JSON string to encode"),
    strategy: Optional[str] = typer.Option(None, help="Force a specific strategy"),
    model: Optional[str] = typer.Option(None, help="Target model for token counting"),
) -> None:
    """Compress a JSON string and print the result."""
    sys.path.insert(0, str(Path(__file__).parent))
    from services.token_optimizer import TokenOptimizer

    try:
        obj = json.loads(payload)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid JSON: {exc}[/red]")
        raise typer.Exit(1)

    optimizer = TokenOptimizer()
    result = optimizer.optimize(
        obj,
        model=model,
        enabled_strategies=[strategy] if strategy else None,
    )

    console.print(result.winner.encoded)
    console.print(
        f"\n[dim]Strategy: {result.winner.strategy} | "
        f"Tokens: {result.winner.token_estimate} | "
        f"Savings: {result.winner.savings_vs_json_pct:+.1f}%[/dim]",
        err=True,
    )


# ── pricing ───────────────────────────────────────────────────────────────────

@app.command()
def pricing() -> None:
    """Show the current model pricing table."""
    sys.path.insert(0, str(Path(__file__).parent))
    from services.pricing import _PRICES

    table = Table(title="Axon Model Pricing (USD per 1k tokens)", show_lines=True)
    table.add_column("Model", style="cyan")
    table.add_column("Input $/1k", justify="right")
    table.add_column("Output $/1k", justify="right")

    for model_name, price in sorted(_PRICES.items()):
        table.add_row(model_name, f"${price.input:.5f}", f"${price.output:.5f}")

    console.print(table)


# ── session ───────────────────────────────────────────────────────────────────

@session_app.command("show")
def session_show(
    session_id: str = typer.Argument(..., help="Session ID to inspect"),
    server: str = typer.Option("http://localhost:8080", help="Axon server URL"),
    limit: int = typer.Option(20, help="Max events to show"),
) -> None:
    """Print the event history for a session."""
    import urllib.request

    url = f"{server}/memory/session/{session_id}?limit={limit}"
    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        console.print(f"[red]Failed to fetch session: {exc}[/red]")
        raise typer.Exit(1)

    console.print_json(json.dumps(data))


@session_app.command("clear")
def session_clear(
    session_id: str = typer.Argument(..., help="Session ID to delete"),
    server: str = typer.Option("http://localhost:8080", help="Axon server URL"),
    confirm: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a session from persistent storage."""
    import urllib.request

    if not confirm:
        typer.confirm(f"Delete session '{session_id}'?", abort=True)

    req = urllib.request.Request(
        f"{server}/memory/session/{session_id}", method="DELETE"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            console.print(f"[green]Session '{session_id}' deleted.[/green]")
    except Exception as exc:
        console.print(f"[red]Failed to delete session: {exc}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
