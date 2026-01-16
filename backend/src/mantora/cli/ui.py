"""Shared UI components for the Mantora CLI."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# Custom theme for Mantora CLI
theme = Theme(
    {
        "info": "dim cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "tip": "blue",
        "link": "underline blue",
        "heading": "bold cyan",
    }
)

console = Console(theme=theme)
error_console = Console(theme=theme, stderr=True)

MANTORA_LOGO = """
█▀▄▀█ ▄▀█ █▄ █ ▀█▀ █▀█ █▀█ ▄▀█
█ ▀ █ █▀█ █ ▀█  █  █▄█ █▀▄ █▀█
"""


def print_banner(host: str, port: int, config_path: Any) -> None:
    """Print the startup banner with connection details."""

    # Header Panel with Logo and Version
    header = Panel(
        Text(MANTORA_LOGO.strip(), justify="center", style="bold cyan"),
        style="cyan",
        subtitle="[dim]Local Observability for Agentic AI[/dim]",
        padding=(1, 2),
    )
    console.print(header)
    console.print()

    # Connection Details Table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold white", justify="right")
    table.add_column("Value", style="cyan")

    ui_url = f"http://{host}:{port}"

    table.add_row("UI Server", f"[link={ui_url}]{ui_url}[/link]")
    table.add_row("Config", str(config_path))

    console.print(
        Panel(table, title="[bold]Active Session[/bold]", border_style="dim white", padding=(1, 1))
    )
    console.print()

    # Quickstart Tips Panel
    tips = Table(show_header=False, box=None, padding=(0, 1))
    tips.add_column("Icon", style="yellow")
    tips.add_column("Command", style="white")

    tips.add_row("✨", "mantora demo duckdb [dim](seed sample data)[/dim]")
    tips.add_row("🦆", "mantora mcp --connector duckdb --db ./demo.duckdb")
    tips.add_row("🐘", "mantora mcp --connector postgres --dsn postgresql://localhost/db")

    console.print(
        Panel(
            tips,
            title="[bold yellow]Connect via MCP[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )
    console.print("  [dim]Add these commands to your mcp.json[/dim]")
    console.print()  # Add spacing before server logs start


def print_error(title: str, message: str, tip: str | None = None) -> None:
    """Print a styled error message with an optional actionable tip."""
    content = Text()
    content.append(f"{message}\n", style="white")

    if tip:
        content.append("\n💡 Tip: ", style="bold blue")
        content.append(tip, style="blue")

    error_console.print(
        Panel(
            content,
            title=f"[bold red]Error: {title}[/bold red]",
            border_style="red",
            padding=(1, 1),
        )
    )


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")
