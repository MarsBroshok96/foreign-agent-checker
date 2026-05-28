"""Command-line interface for the deterministic MVP."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from fa_checker.adapters.http_client import HttpFetchError
from fa_checker.adapters.minjust_registry_client import (
    RegistryDownloadError,
    load_minjust_registry_entries,
)
from fa_checker.adapters.rambler_loader import load_rambler_article
from fa_checker.article.extractor import ArticleExtractionError
from fa_checker.config import get_settings
from fa_checker.pipeline import run_offline_check
from fa_checker.registry.repository import load_registry_from_xlsx
from fa_checker.reporting.json_report import report_to_json
from fa_checker.reporting.markdown_report import report_to_markdown

app = typer.Typer(
    add_completion=False,
    help="Check a Rambler article against the official foreign-agent registry.",
)
console = Console()
status_console = Console(stderr=True)


@app.command()
def main(
    url: Annotated[str | None, typer.Argument(help="Rambler article URL to check.")] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format",
            help="Report output format: markdown or json.",
        ),
    ] = "markdown",
    registry_path: Annotated[
        Path | None,
        typer.Option(
            "--registry-path",
            help="Path to a local Minjust registry XLSX file.",
        ),
    ] = None,
    force_refresh_registry: Annotated[
        bool,
        typer.Option(
            "--force-refresh-registry",
            help="Refresh cached Minjust registry snapshot before loading.",
        ),
    ] = False,
    registry_cache_dir: Annotated[
        Path | None,
        typer.Option(
            "--registry-cache-dir",
            help="Directory for cached Minjust registry snapshots.",
        ),
    ] = None,
    registry_cache_ttl_hours: Annotated[
        int | None,
        typer.Option(
            "--registry-cache-ttl-hours",
            help="Registry cache time-to-live in hours.",
        ),
    ] = None,
) -> None:
    """Run deterministic article check and render a report."""
    if output_format not in {"markdown", "json"}:
        status_console.print("[red]Error:[/red] --output-format must be 'markdown' or 'json'.")
        raise typer.Exit(1)

    settings = get_settings()
    article_url = url or typer.prompt("Rambler article URL")

    try:
        status_console.print("[cyan]Loading Rambler article...[/cyan]")
        article = load_rambler_article(article_url)

        status_console.print("[cyan]Loading Minjust registry...[/cyan]")
        if registry_path is not None:
            registry_entries = load_registry_from_xlsx(
                path=registry_path,
                registry_source_url=settings.minjust_registry_url,
            )
        else:
            registry_entries = load_minjust_registry_entries(
                cache_dir=registry_cache_dir or settings.registry_cache_dir,
                registry_page_url=settings.minjust_registry_url,
                ttl_hours=(
                    registry_cache_ttl_hours
                    if registry_cache_ttl_hours is not None
                    else settings.registry_cache_ttl_hours
                ),
                force_refresh=force_refresh_registry,
            )

        status_console.print("[cyan]Running deterministic check...[/cyan]")
        report = run_offline_check(article, registry_entries)

        status_console.print("[cyan]Rendering report...[/cyan]")
        rendered = (
            report_to_json(report)
            if output_format == "json"
            else report_to_markdown(report)
        )
        console.print(rendered, markup=False, soft_wrap=True)
    except (
        ValueError,
        HttpFetchError,
        ArticleExtractionError,
        RegistryDownloadError,
        OSError,
    ) as exc:
        status_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
