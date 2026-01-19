"""Config loader for Mantora proxy and app settings.

Search order: ./config.toml -> ./mantora.toml -> platform config -> legacy ~/.mantora/config.toml
Uses stdlib tomllib (Python 3.11+).
"""

from __future__ import annotations

import os
import platform
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from mantora.config.settings import LimitsConfig, PolicyConfig, SafetyMode, Settings


class TargetConfig(BaseModel):
    """Configuration for the target MCP server to proxy."""

    type: str = Field(default="generic", description="Target type for adapter selection")
    command: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)


class ProxyConfig(BaseModel):
    """Configuration for the MCP proxy."""

    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    target: TargetConfig = Field(default_factory=TargetConfig)
    sqlite_path: Path | None = None
    project_root: Path | None = None
    tag: str | None = None


_LEGACY_CONFIG_PATH = Path.home() / ".mantora" / "config.toml"


def get_platform_config_path() -> Path:
    """Return the platform-specific config.toml path."""
    system = platform.system().lower()
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "mantora" / "config.toml"
    if system == "windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "mantora" / "config.toml"
        return Path.home() / "AppData" / "Roaming" / "mantora" / "config.toml"

    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "mantora" / "config.toml"
    return Path.home() / ".config" / "mantora" / "config.toml"


def get_config_search_paths() -> list[Path]:
    """Return config search paths in priority order."""
    return [
        Path("./config.toml"),
        Path("./mantora.toml"),
        get_platform_config_path(),
        _LEGACY_CONFIG_PATH,
    ]


def _find_config_file() -> Path | None:
    """Find the first existing config file in search order."""
    for path in get_config_search_paths():
        if path.exists():
            return path
    return None


def _parse_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML file and return its contents."""
    with path.open("rb") as f:
        return tomllib.load(f)


def resolve_config_path(config_path: Path | None = None) -> Path:
    """Resolve the config path used for display or creation."""
    if config_path:
        return config_path
    return _find_config_file() or get_platform_config_path()


def _build_policy_config(data: Mapping[str, Any]) -> PolicyConfig:
    policy_data = dict(data.get("policy", {}))

    if "safety_mode" in data and "protective_mode" not in policy_data:
        safety_mode = SafetyMode(data["safety_mode"])
        policy_data["protective_mode"] = safety_mode == SafetyMode.protective

    return PolicyConfig.model_validate(policy_data)


def _build_limits_config(data: Mapping[str, Any]) -> LimitsConfig:
    limits_data = dict(data.get("limits", {}))

    if "preview_rows" not in limits_data and "max_preview_rows" in limits_data:
        limits_data["preview_rows"] = limits_data.pop("max_preview_rows")

    if "preview_bytes" not in limits_data and "max_preview_payload_bytes" in limits_data:
        limits_data["preview_bytes"] = limits_data.pop("max_preview_payload_bytes")

    if "preview_columns" not in limits_data and "max_columns" in limits_data:
        limits_data["preview_columns"] = limits_data.pop("max_columns")

    return LimitsConfig.model_validate(limits_data)


def merge_cli_overrides(config: ProxyConfig, overrides: Mapping[str, Any]) -> ProxyConfig:
    """Apply CLI overrides to an existing proxy config."""
    if "protective_mode" in overrides and overrides["protective_mode"] is not None:
        config.policy.protective_mode = bool(overrides["protective_mode"])

    if "sqlite_path" in overrides and overrides["sqlite_path"] is not None:
        config.sqlite_path = Path(overrides["sqlite_path"])

    if "project_root" in overrides and overrides["project_root"] is not None:
        config.project_root = Path(overrides["project_root"])

    if "tag" in overrides and overrides["tag"] is not None:
        config.tag = str(overrides["tag"])

    return config


def load_proxy_config(
    config_path: Path | None = None, *, cli_overrides: Mapping[str, Any] | None = None
) -> ProxyConfig:
    """Load proxy configuration from TOML file.

    Args:
        config_path: Explicit path to config file. If None, searches default locations.
        cli_overrides: Optional CLI overrides to apply after loading.

    Returns:
        ProxyConfig with loaded or default values.

    Raises:
        FileNotFoundError: If an explicit config_path is provided but does not exist.
    """
    if config_path:
        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found at explicitly provided path: {config_path}. "
                "Ensure the file exists or omit the argument to use default search paths."
            )
        path: Path = config_path
    else:
        found_path = _find_config_file()
        if found_path is None:
            config = ProxyConfig()
            if cli_overrides:
                config = merge_cli_overrides(config, cli_overrides)
            return config
        path = found_path

    try:
        data = _parse_toml(path)
    except Exception as e:
        raise RuntimeError(f"Failed to parse configuration file at {path}: {e}") from e

    # Extract proxy-relevant sections
    proxy_data: dict[str, Any] = {
        "policy": _build_policy_config(data),
        "limits": _build_limits_config(data),
    }

    if "target" in data:
        proxy_data["target"] = data["target"]

    if "sqlite_path" in data:
        db_path = Path(data["sqlite_path"])
        # Resolve relative paths against the config file location
        if not db_path.is_absolute():
            db_path = path.parent / db_path
        proxy_data["sqlite_path"] = db_path

    if "project_root" in data:
        project_root = Path(data["project_root"])
        if not project_root.is_absolute():
            project_root = path.parent / project_root
        proxy_data["project_root"] = project_root

    if "tag" in data:
        proxy_data["tag"] = data["tag"]

    config = ProxyConfig.model_validate(proxy_data)
    if cli_overrides:
        config = merge_cli_overrides(config, cli_overrides)
    return config


def load_settings(
    config_path: Path | None = None, *, cli_overrides: Mapping[str, Any] | None = None
) -> Settings:
    """Load application settings from TOML file."""
    if config_path:
        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found at explicitly provided path: {config_path}. "
                "Ensure the file exists or omit the argument to use default search paths."
            )
        path: Path = config_path
    else:
        found_path = _find_config_file()
        if found_path is None:
            return Settings()
        path = found_path

    try:
        data = _parse_toml(path)
    except Exception as e:
        raise RuntimeError(f"Failed to parse configuration file at {path}: {e}") from e

    settings_data: dict[str, Any] = {
        "policy": _build_policy_config(data),
        "limits": _build_limits_config(data),
    }

    if "cors_allow_origins" in data:
        settings_data["cors_allow_origins"] = data["cors_allow_origins"]

    if "sqlite_path" in data:
        db_path = Path(data["sqlite_path"])
        if not db_path.is_absolute():
            db_path = path.parent / db_path
        settings_data["storage"] = {"sqlite_path": db_path}

    settings = Settings.model_validate(settings_data)

    if cli_overrides:
        if "protective_mode" in cli_overrides and cli_overrides["protective_mode"] is not None:
            settings.policy.protective_mode = bool(cli_overrides["protective_mode"])
        if "preview_rows" in cli_overrides and cli_overrides["preview_rows"] is not None:
            settings.limits.preview_rows = int(cli_overrides["preview_rows"])
        if "preview_bytes" in cli_overrides and cli_overrides["preview_bytes"] is not None:
            settings.limits.preview_bytes = int(cli_overrides["preview_bytes"])

    return settings
