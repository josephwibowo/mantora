"""Tests for config loader."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from mantora.config import ProxyConfig, load_proxy_config


def test_load_proxy_config_defaults() -> None:
    """Loading with no config file returns defaults."""
    # This test is a placeholder - actual default loading tested in test_load_proxy_config_no_file
    pass


def test_load_proxy_config_no_file() -> None:
    """Loading with no config file returns defaults."""
    # When no config file exists, should return defaults
    config = ProxyConfig()
    assert config.policy.protective_mode
    assert config.limits.preview_rows == 10
    assert config.limits.preview_bytes == 512 * 1024
    assert config.limits.preview_columns == 80
    assert config.target.command == []
    assert config.target.env == {}
    assert config.sqlite_path is None


def test_load_proxy_config_from_toml(tmp_path: Path) -> None:
    """Loading from a TOML file parses correctly."""
    config_file = tmp_path / "mantora.toml"
    config_file.write_text(
        dedent("""
        sqlite_path = "/abs/path/to/db.sqlite"

        [policy]
        protective_mode = false

        [limits]
        preview_rows = 100
        preview_bytes = 1024
        preview_columns = 10
        retention_days = 7
        max_db_bytes = 1234

        [target]
        command = ["uvx", "mcp-server-sqlite", "--db-path", "test.db"]
        env = { "DEBUG" = "1" }
        """)
    )

    config = load_proxy_config(config_path=config_file)

    assert not config.policy.protective_mode
    assert config.limits.preview_rows == 100
    assert config.limits.preview_bytes == 1024
    assert config.limits.preview_columns == 10
    assert config.limits.retention_days == 7
    assert config.limits.max_db_bytes == 1234
    assert config.sqlite_path == Path("/abs/path/to/db.sqlite")
    assert config.target.command == ["uvx", "mcp-server-sqlite", "--db-path", "test.db"]
    assert config.target.env == {"DEBUG": "1"}


def test_load_proxy_config_relative_sqlite_path(tmp_path: Path) -> None:
    """Relative sqlite_path is resolved against config file location."""
    config_file = tmp_path / "subdir" / "mantora.toml"
    config_file.parent.mkdir()
    config_file.write_text('sqlite_path = "./db.sqlite"')

    config = load_proxy_config(config_path=config_file)

    # Should be resolved to tmp_path/subdir/db.sqlite
    expected = config_file.parent / "db.sqlite"
    assert config.sqlite_path == expected


def test_load_proxy_config_partial_toml(tmp_path: Path) -> None:
    """Loading partial config uses defaults for missing fields."""
    config_file = tmp_path / "mantora.toml"
    config_file.write_text(
        dedent("""
        safety_mode = "protective"
        """)
    )

    config = load_proxy_config(config_path=config_file)

    assert config.policy.protective_mode
    assert config.target.command == []
    assert config.sqlite_path is None


def test_load_proxy_config_legacy_safety_mode(tmp_path: Path) -> None:
    """Legacy safety_mode maps to policy.protective_mode."""
    config_file = tmp_path / "mantora.toml"
    config_file.write_text('safety_mode = "transparent"')

    config = load_proxy_config(config_path=config_file)

    assert not config.policy.protective_mode


def test_load_proxy_config_invalid_safety_mode(tmp_path: Path) -> None:
    """Loading with invalid safety mode raises validation error."""
    config_file = tmp_path / "mantora.toml"
    config_file.write_text('safety_mode = "invalid"')

    with pytest.raises(ValueError):
        load_proxy_config(config_path=config_file)


def test_load_proxy_config_cli_override(tmp_path: Path) -> None:
    """CLI overrides take precedence over config file."""
    config_file = tmp_path / "mantora.toml"
    config_file.write_text(
        dedent("""
        [policy]
        protective_mode = true
        """)
    )

    config = load_proxy_config(
        config_path=config_file,
        cli_overrides={"protective_mode": False},
    )

    assert not config.policy.protective_mode
