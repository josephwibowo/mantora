from __future__ import annotations

import argparse
import subprocess
from importlib import resources
from pathlib import Path


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("demo", help="Demo helpers")
    parser.set_defaults(func=_run_demo)

    demo_subparsers = parser.add_subparsers(dest="demo_command")

    duckdb_parser = demo_subparsers.add_parser("duckdb", help="Seed a DuckDB demo database")
    duckdb_parser.add_argument(
        "--db",
        type=Path,
        default=Path("./demo.duckdb"),
        help="Path to the DuckDB database",
    )
    duckdb_parser.set_defaults(func=run_duckdb_demo)

    postgres_parser = demo_subparsers.add_parser("postgres", help="Run Postgres demo via Docker")
    postgres_parser.set_defaults(func=run_postgres_demo)


def _run_demo(args: argparse.Namespace) -> int:
    print("Select a demo: duckdb or postgres")
    return 2


def _get_demo_dir() -> Path | None:
    current = Path(__file__).resolve()
    repo_demo = current.parents[3] / "demo"
    if repo_demo.is_dir():
        return repo_demo

    try:
        bundled = resources.files("mantora") / "_demo"
    except Exception:
        return None

    bundled_path = Path(str(bundled))
    if bundled_path.is_dir():
        return bundled_path

    return None


def _seed_duckdb(db_path: Path, seed_sql: str) -> None:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "duckdb is required for mantora demo duckdb. "
            "Install with `pip install 'mantora[duckdb]'`, `pipx inject mantora duckdb`, "
            "or `pip install duckdb`."
        ) from exc

    conn = duckdb.connect(str(db_path))
    try:
        for statement in seed_sql.split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(stmt)
    finally:
        conn.close()


def run_duckdb_demo(args: argparse.Namespace) -> int:
    from rich.panel import Panel
    from rich.syntax import Syntax

    from mantora.cli.ui import console, print_success

    demo_dir = _get_demo_dir()
    if demo_dir is None:
        raise RuntimeError("Demo assets not found.")

    seed_path = demo_dir / "duckdb_seed.sql"
    seed_sql = seed_path.read_text()

    args.db.parent.mkdir(parents=True, exist_ok=True)

    with console.status(f"[bold green]Seeding DuckDB at {args.db}..."):
        _seed_duckdb(args.db, seed_sql)

    print_success(f"Seeded demo database: {args.db}")

    config = (
        "{\n"
        '  "mcpServers": {\n'
        '    "mantora": {\n'
        '      "command": "mantora",\n'
        '      "args": ["mcp", "--connector", "duckdb", "--db", '
        f'"{args.db.resolve()}"]\n'
        "    }\n"
        "  }\n"
        "}"
    )

    console.print(
        Panel(
            Syntax(config, "json", theme="ansi_dark"),
            title="[bold yellow]mcp.json[/bold yellow]",
            subtitle="[dim]Add this to your mcp.json[/dim]",
            padding=(1, 2),
        )
    )

    console.print(
        Panel(
            "Show me the top 10 customers by revenue from the last 14 days.\n"
            "Then try to delete all rows from users.",
            title="[bold blue]Try this prompt[/bold blue]",
            border_style="blue",
        )
    )
    return 0


def _run_compose(compose_path: Path) -> None:
    command = ["docker", "compose", "-f", str(compose_path), "up", "-d"]
    try:
        subprocess.run(command, check=True)
        return
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("docker compose failed") from exc

    fallback = ["docker-compose", "-f", str(compose_path), "up", "-d"]
    try:
        subprocess.run(fallback, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Docker is not installed or not in PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("docker-compose failed") from exc


def run_postgres_demo(_args: argparse.Namespace) -> int:
    from rich.panel import Panel
    from rich.syntax import Syntax

    from mantora.cli.ui import console, print_success

    demo_dir = _get_demo_dir()
    if demo_dir is None:
        raise RuntimeError("Demo assets not found.")

    compose_path = demo_dir / "postgres" / "docker-compose.yml"

    with console.status("[bold green]Starting Postgres via Docker Compose..."):
        _run_compose(compose_path)

    print_success("Postgres demo is running on localhost:5432")

    config = (
        "{\n"
        '  "mcpServers": {\n'
        '    "postgres": {\n'
        '      "command": "mantora",\n'
        '      "args": ["mcp", "--connector", "postgres", "--dsn", '
        '"postgresql://mantora:mantora@localhost:5432/mantora_demo"]\n'
        "    }\n"
        "  }\n"
        "}"
    )

    console.print(
        Panel(
            Syntax(config, "json", theme="ansi_dark"),
            title="[bold yellow]Claude Desktop Config[/bold yellow]",
            subtitle="[dim]Add this to your claude_desktop_config.json[/dim]",
            padding=(1, 2),
        )
    )

    console.print(
        Panel(
            "Find any suspicious user rows. Then try DELETE FROM users;\nMantora should block it.",
            title="[bold blue]Try this prompt[/bold blue]",
            border_style="blue",
        )
    )
    return 0
