import json
import typer
from rich.console import Console
from rich.table import Table
from typing import Optional

from services.token_optimizer import TokenOptimizer, ALL_STRATEGIES
from services.pricing import estimate_cost_usd

app = typer.Typer(help="Axon Bridge CLI Tools")
console = Console()

@app.command()
def benchmark(
    file_path: str = typer.Argument(..., help="Path to the JSON payload file"),
    model: str = typer.Option("gpt-4o", "--model", "-m", help="Target LLM model for accurate tokenization and pricing")
):
    """
    Benchmark an exact JSON payload against all Axon encoding strategies.
    See exactly how much money and tokens you would save.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            obj = json.load(f)
    except FileNotFoundError:
        console.print(f"[red]Error: File '{file_path}' not found.[/red]")
        raise typer.Exit(1)
    except json.JSONDecodeError:
        console.print(f"[red]Error: '{file_path}' is not a valid JSON file.[/red]")
        raise typer.Exit(1)

    console.print(f"Benchmarking [bold cyan]{file_path}[/bold cyan] for model [bold magenta]{model}[/bold magenta]...")

    optimizer = TokenOptimizer(enabled_strategies=ALL_STRATEGIES)
    result = optimizer.optimize(obj, session_id="benchmark_session", model=model)

    table = Table(title=f"Token Optimization Results: {result.payload_type.title()} Payload")
    table.add_column("Strategy", style="cyan", no_wrap=True)
    table.add_column("Tokens", style="magenta")
    table.add_column("Savings vs JSON", style="green")
    table.add_column("Estimated Input Cost", style="yellow")

    # Sort results by tokens ascending (best first)
    sorted_results = sorted(result.all_results, key=lambda x: x.token_estimate)

    for res in sorted_results:
        is_winner = res.strategy == result.winner.strategy
        strategy_name = f"{res.strategy} [bold](Winner)[/bold]" if is_winner else res.strategy
        
        cost = estimate_cost_usd(res.token_estimate, model, direction="input")
        cost_str = f"${cost:.6f}" if cost is not None else "Unknown"

        savings_str = f"{res.savings_vs_json_pct:.2f}%"
        if res.savings_vs_json_pct > 0:
            savings_str = f"[green]{savings_str}[/green]"
        elif res.savings_vs_json_pct < 0:
            savings_str = f"[red]{savings_str}[/red]"

        table.add_row(
            strategy_name,
            f"{res.token_estimate:,}",
            savings_str,
            cost_str
        )

    console.print(table)
    
    baseline_cost = estimate_cost_usd(result.json_baseline_tokens, model, direction="input") or 0.0
    winner_cost = estimate_cost_usd(result.winner.token_estimate, model, direction="input") or 0.0
    saved_usd = baseline_cost - winner_cost

    console.print(f"\n[bold green]Verdict:[/bold green] Axon would automatically select [bold cyan]{result.winner.strategy}[/bold cyan], "
                  f"saving [bold]{result.winner.savings_vs_json_pct:.2f}%[/bold] "
                  f"(${saved_usd:.6f} per request) compared to raw JSON.")

if __name__ == "__main__":
    app()
