from __future__ import annotations

import argparse
import os

from mantora.cli.demo import configure_parser as configure_demo
from mantora.cli.mcp import configure_parser as configure_mcp
from mantora.cli.up import configure_parser as configure_up


def build_parser() -> argparse.ArgumentParser:
    from mantora import __version__

    parser = argparse.ArgumentParser(
        prog="mantora",
        description="Mantora CLI (UI server + MCP proxy)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Print version and exit",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Print full traceback on errors (or set MANTORA_TRACE=1)",
    )
    subparsers = parser.add_subparsers(dest="command")

    configure_up(subparsers)
    configure_mcp(subparsers)
    configure_demo(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 2

    want_trace = bool(getattr(args, "trace", False)) or os.environ.get("MANTORA_TRACE") in {
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    }
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        # Keep Ctrl-C quiet by default.
        return 130
    except (RuntimeError, Exception) as exc:
        if want_trace:
            from rich.console import Console

            Console().print_exception()
        else:
            # Import locally to avoid slow import on happy path
            from mantora.cli.ui import print_error

            # Simple heuristic to extract tips from common errors
            tip = "re-run with --trace to see the full traceback."
            if "Connection refused" in str(exc):
                tip = "Ensure the target server (e.g., Docker container) is running."
            elif "No such file or directory" in str(exc) and "mantora.toml" in str(exc):
                tip = "Check that your config file path is correct."

            print_error(type(exc).__name__, str(exc), tip=tip)
        return 1
