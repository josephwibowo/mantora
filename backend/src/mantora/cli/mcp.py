from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import sys
from pathlib import Path

from mantora.config import ProxyConfig, TargetConfig, load_proxy_config
from mantora.mcp import MCPProxy, PolicyHooks
from mantora.store.sqlite import SQLiteSessionStore

logger = logging.getLogger(__name__)


def configure_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser("mcp", help="Run the MCP proxy")
    parser.set_defaults(func=run_mcp)
    parser.add_argument("--config", type=Path, help="Path to config.toml")
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Project root for git context detection (default: auto-detect from cwd)",
    )
    parser.add_argument(
        "--tag",
        help="Optional session tag for filtering and PR receipts (e.g., JIRA ticket)",
    )
    parser.add_argument(
        "--connector",
        choices=["duckdb", "postgres"],
        help="Connector type for the target MCP server",
    )
    parser.add_argument("--db", type=Path, help="DuckDB database path")
    parser.add_argument("--dsn", help="Postgres DSN")
    parser.add_argument("--session", help="Session name to use")
    parser.add_argument(
        "--protective",
        choices=["on", "off"],
        help="Override protective mode",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")


def _parse_protective(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() == "on"


def build_target_command(connector: str, db: Path | None, dsn: str | None) -> list[str]:
    if connector == "duckdb":
        if db is None:
            raise ValueError("--db is required for duckdb connector")
        # Prefer the console-script next to Mantora's Python executable (pipx),
        # since Cursor's PATH may not include the venv bin directory.
        # NOTE: Don't use `.resolve()` here: venv `python` is often a symlink to the base
        # interpreter, and resolving would jump out of the venv and miss console scripts
        # installed into the venv's `bin/`.
        local_bin = Path(sys.executable).parent / "mcp-server-duckdb"
        if local_bin.exists():
            return [str(local_bin), "--db", str(db)]
        path_bin = shutil.which("mcp-server-duckdb")
        if path_bin is None:
            raise RuntimeError(
                "mcp-server-duckdb is required for the duckdb connector. "
                "Install with `pip install 'mantora[duckdb]'`, "
                "`pipx inject mantora mcp-server-duckdb`, or `pip install mcp-server-duckdb`."
            )
        return [path_bin, "--db", str(db)]
    if connector == "postgres":
        if not dsn:
            raise ValueError("--dsn is required for postgres connector")
        local_bin = Path(sys.executable).parent / "mcp-server-postgres"
        if local_bin.exists():
            return [str(local_bin), "--dsn", dsn]
        path_bin = shutil.which("mcp-server-postgres")
        if path_bin is None:
            raise RuntimeError(
                "mcp-server-postgres is required for the postgres connector. "
                "Install with `pip install 'mantora[postgres]'`, "
                "`pipx inject mantora mcp-server-postgres`, "
                "or `pip install mcp-server-postgres`."
            )
        return [path_bin, "--dsn", dsn]

    raise ValueError(f"Unsupported connector: {connector}")


def _resolve_store_path(config: ProxyConfig, explicit: Path | None) -> Path:
    if explicit:
        return explicit
    env_path = os.environ.get("MANTORA_STORAGE__SQLITE__PATH")
    if env_path:
        return Path(env_path)
    if config.sqlite_path:
        return config.sqlite_path
    return Path.home() / ".mantora" / "sessions.db"


def _apply_connector(args: argparse.Namespace, config: ProxyConfig) -> None:
    if args.connector:
        command = build_target_command(args.connector, args.db, args.dsn)
        config.target = TargetConfig(type=args.connector, command=command)
        return

    if not config.target.command:
        raise ValueError("No target connector configured. Use --connector or config target.")


def _print_startup(config: ProxyConfig, session_id: str | None) -> None:
    # Use stderr for logs since stdout is used for MCP JSON-RPC
    # We'll use our error_console which writes to stderr
    from rich.panel import Panel
    from rich.table import Table

    from mantora.cli.ui import error_console as console

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold white", justify="right")
    table.add_column("Value", style="cyan")

    mode = (
        "[bold green]ON[/bold green]"
        if config.policy.protective_mode
        else "[bold red]OFF[/bold red]"
    )
    table.add_row("Protective Mode", mode)

    if config.policy.protective_mode:
        rules = []
        if config.policy.block_ddl:
            rules.append("block_ddl")
        if config.policy.block_dml:
            rules.append("block_dml")
        if config.policy.block_multi_statement:
            rules.append("block_multi_statement")
        if config.policy.block_delete_without_where:
            rules.append("block_delete_without_where")

        if rules:
            table.add_row("Active Rules", ", ".join(rules))

    if session_id:
        table.add_row("Session ID", session_id)

    if config.target.type:
        table.add_row("Connector", config.target.type)

    console.print(
        Panel(
            table,
            title="[bold]MCP Proxy Ready[/bold]",
            subtitle="[dim]Forwarding JSON-RPC over stdio[/dim]",
            border_style="dim white",
            padding=(1, 1),
        )
    )


def _build_proxy(config: ProxyConfig, store_path: Path, session_title: str | None) -> MCPProxy:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteSessionStore(
        store_path,
        retention_days=config.limits.retention_days,
        max_db_bytes=config.limits.max_db_bytes,
    )
    hooks = PolicyHooks(
        config=config,
        policy=config.policy,
        limits=config.limits,
        target_type=config.target.type,
    )
    proxy = MCPProxy(config=config, store=store, hooks=hooks)

    session_id = proxy.start_session(session_title) if session_title else None

    _print_startup(config, session_id)
    return proxy


def _run_proxy(config: ProxyConfig, store_path: Path, session_title: str | None) -> None:
    proxy = _build_proxy(config, store_path, session_title)

    async def runner() -> None:
        try:
            await proxy.run()
        except KeyboardInterrupt:
            logger.info("Proxy stopped by user")
        except Exception as exc:
            logger.error("Proxy error: %s", exc, exc_info=True)
            raise
        finally:
            store = proxy.store
            if isinstance(store, SQLiteSessionStore):
                store.close()

    asyncio.run(runner())


def run_mcp(args: argparse.Namespace) -> int:
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    protective = _parse_protective(args.protective)
    config = load_proxy_config(
        args.config,
        cli_overrides={
            "protective_mode": protective,
            "project_root": args.project_root,
            "tag": args.tag,
        },
    )

    _apply_connector(args, config)

    store_path = _resolve_store_path(config, explicit=None)
    _run_proxy(config, store_path, args.session)
    return 0


def run_proxy() -> None:
    """Legacy entrypoint for mantora-proxy."""
    parser = argparse.ArgumentParser(
        description="Run the Mantora MCP observability proxy (deprecated)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mantora-proxy                           # Use default config locations
  mantora-proxy /path/to/mantora.toml     # Use specific config file

Configuration:
  The proxy looks for config in these locations (in order):
  1. Provided config_path argument
  2. ./config.toml
  3. ./mantora.toml (legacy)
  4. platform config.toml
        """,
    )
    parser.add_argument(
        "config_path",
        nargs="?",
        type=Path,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Override session database path (default: ~/.mantora/sessions.db)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.warning("mantora-proxy is deprecated. Use `mantora mcp` instead.")

    config = load_proxy_config(args.config_path)
    store_path = _resolve_store_path(config, explicit=args.db_path)
    _run_proxy(config, store_path, session_title=None)
