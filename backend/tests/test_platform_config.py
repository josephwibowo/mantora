"""Tests for platform config path detection."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

from mantora.config import get_platform_config_path


def test_get_platform_config_path_darwin(monkeypatch: Any) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    path = get_platform_config_path()
    assert path == (Path.home() / "Library" / "Application Support" / "mantora" / "config.toml")


def test_get_platform_config_path_linux(monkeypatch: Any) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/tmp/config")
    path = get_platform_config_path()
    assert path == Path("/tmp/config") / "mantora" / "config.toml"


def test_get_platform_config_path_windows(monkeypatch: Any) -> None:
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", "C:/Users/Test/AppData/Roaming")
    path = get_platform_config_path()
    assert path == Path("C:/Users/Test/AppData/Roaming") / "mantora" / "config.toml"
