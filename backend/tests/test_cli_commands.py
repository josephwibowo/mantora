"""Tests for CLI command parsing."""

from __future__ import annotations

from pathlib import Path

from mantora.cli.demo import run_duckdb_demo, run_postgres_demo
from mantora.cli.main import build_parser
from mantora.cli.mcp import run_mcp
from mantora.cli.up import run_up


def test_up_command_parsing() -> None:
    parser = build_parser()
    args = parser.parse_args(["up", "--port", "3033", "--no-open"])

    assert args.command == "up"
    assert args.port == 3033
    assert args.open_browser is False
    assert args.func is run_up


def test_mcp_command_parsing() -> None:
    parser = build_parser()
    args = parser.parse_args(["mcp", "--connector", "duckdb", "--db", "demo.duckdb"])

    assert args.command == "mcp"
    assert args.connector == "duckdb"
    assert args.db == Path("demo.duckdb")
    assert args.func is run_mcp


def test_demo_duckdb_routing() -> None:
    parser = build_parser()
    args = parser.parse_args(["demo", "duckdb"])

    assert args.command == "demo"
    assert args.demo_command == "duckdb"
    assert args.func is run_duckdb_demo


def test_demo_postgres_routing() -> None:
    parser = build_parser()
    args = parser.parse_args(["demo", "postgres"])

    assert args.command == "demo"
    assert args.demo_command == "postgres"
    assert args.func is run_postgres_demo
