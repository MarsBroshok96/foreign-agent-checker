"""Command-line interface for the scaffolded checker."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fa_checker.pipeline import run_check

app = typer.Typer(
    add_completion=False,
    help="Check a Rambler article against the official foreign-agent registry.",
)
console = Console()


PLANNED_STAGES = [
    "Validate article URL",
    "Load Rambler article",
    "Extract article text and metadata",
    "Load official Minjust registry snapshot",
    "Generate deterministic candidates",
    "Run bounded agent review",
    "Compute deterministic risk score",
    "Generate JSON and Markdown reports",
]


@app.command()
def main(
    url: Annotated[str | None, typer.Argument(help="Rambler article URL to check.")] = None,
) -> None:
    """Run the scaffolded checker without making network calls."""
    article_url = url or typer.prompt("Rambler article URL")

    console.print(Panel.fit("Foreign Agent Checker scaffold", style="bold cyan"))
    console.print(f"[bold]Article URL:[/bold] {article_url}")
    console.print()

    table = Table(title="Planned pipeline stages")
    table.add_column("#", justify="right")
    table.add_column("Stage")
    table.add_column("Current behavior")

    for index, stage in enumerate(PLANNED_STAGES, start=1):
        table.add_row(str(index), stage, "placeholder")

    console.print(table)
    report = run_check(article_url)

    console.print()
    console.print(f"[bold]Status:[/bold] {report.status.value}")
    for limitation in report.limitations:
        console.print(f"[yellow]Limitation:[/yellow] {limitation}")
    console.print("[bold green]Scaffold is ready.[/bold green]")
