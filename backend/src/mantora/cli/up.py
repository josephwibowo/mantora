from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import webbrowser
from pathlib import Path

import uvicorn

from mantora.app import create_app
from mantora.config import load_settings, resolve_config_path


def _is_shutdown_noise(exc: BaseException) -> bool:
    if isinstance(exc, asyncio.CancelledError | KeyboardInterrupt | GeneratorExit):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return all(_is_shutdown_noise(sub_exc) for sub_exc in exc.exceptions)
    return False


class NoisyShutdownFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            _, exc, _ = record.exc_info
            if exc is not None and _is_shutdown_noise(exc):
                return False
        return True


def configure_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("up", help="Start the Mantora UI server")
    parser.set_defaults(func=run_up)
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=3030, help="Port to bind")
    parser.add_argument(
        "--open",
        dest="open_browser",
        action="store_true",
        default=True,
        help="Open the browser after startup",
    )
    parser.add_argument(
        "--no-open",
        dest="open_browser",
        action="store_false",
        help="Do not open the browser",
    )
    parser.add_argument("--config", type=Path, help="Path to mantora.toml")


def _print_banner(host: str, port: int, config_path: Path) -> None:
    from mantora.cli.ui import print_banner

    print_banner(host, port, config_path)


def run_up(args: argparse.Namespace) -> int:
    from rich.logging import RichHandler

    from mantora.cli.ui import console

    # Configure root logger with Rich
    # Note: rich_tracebacks=False prevents noisy shutdown tracebacks
    rich_handler = RichHandler(rich_tracebacks=False, markup=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler],
    )

    # Force uvicorn error log to propagate to root (which has RichHandler)
    # We leave access log disabled below, so we don't need to configure it
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

    settings = load_settings(args.config)
    config_path = resolve_config_path(args.config)

    _print_banner(args.host, args.port, config_path)

    if args.open_browser:
        url = f"http://{args.host}:{args.port}"
        webbrowser.open(url)

    rich_handler.addFilter(NoisyShutdownFilter())

    app = create_app(settings=settings)

    # Disable access log by default to reduce noise
    # We already have connection info in the banner
    console.print()  # Final spacer before uvicorn starts

    with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError):
        uvicorn.run(
            app, host=args.host, port=args.port, log_level="info", access_log=False, log_config=None
        )
    return 0
