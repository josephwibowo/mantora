from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SafetyMode(str, Enum):
    protective = "protective"
    transparent = "transparent"


class Caps(BaseModel):
    max_preview_rows: int = 10
    max_preview_payload_bytes: int = 512 * 1024
    max_columns: int = 80


class LimitsConfig(BaseModel):
    preview_rows: int = Field(default=10, ge=1)
    preview_bytes: int = Field(default=512 * 1024, ge=1)
    preview_columns: int = Field(default=80, ge=1)
    retention_days: int = Field(default=14, ge=0)
    max_db_bytes: int = Field(default=0, ge=0)


class PolicyConfig(BaseModel):
    protective_mode: bool = True
    block_ddl: bool = True
    block_dml: bool = True
    block_multi_statement: bool = True
    block_delete_without_where: bool = True


def _default_sqlite_path() -> Path:
    return Path.home() / ".mantora" / "sessions.db"


class StorageBackend(str, Enum):
    memory = "memory"
    sqlite = "sqlite"


class Storage(BaseModel):
    backend: StorageBackend = StorageBackend.sqlite
    sqlite_path: Path = Field(default_factory=_default_sqlite_path)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3030",
            "http://127.0.0.1:3030",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    enable_raw_debug_ring_buffer: bool = False
    storage: Storage = Field(default_factory=Storage)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        if "safety_mode" in data:
            safety_mode = SafetyMode(data.pop("safety_mode"))
            if "policy" not in data:
                data["policy"] = {
                    **data.get("policy", {}),
                    "protective_mode": safety_mode == SafetyMode.protective,
                }

        if "caps" in data:
            caps = data.pop("caps")
            if "limits" not in data:
                if isinstance(caps, Caps):
                    data["limits"] = LimitsConfig(
                        preview_rows=caps.max_preview_rows,
                        preview_bytes=caps.max_preview_payload_bytes,
                        preview_columns=caps.max_columns,
                    )
                elif isinstance(caps, dict):
                    data["limits"] = LimitsConfig(
                        preview_rows=caps.get("max_preview_rows", LimitsConfig().preview_rows),
                        preview_bytes=caps.get(
                            "max_preview_payload_bytes", LimitsConfig().preview_bytes
                        ),
                        preview_columns=caps.get("max_columns", LimitsConfig().preview_columns),
                        retention_days=caps.get("retention_days", LimitsConfig().retention_days),
                        max_db_bytes=caps.get("max_db_bytes", LimitsConfig().max_db_bytes),
                    )

        return data

    @property
    def safety_mode(self) -> SafetyMode:
        return SafetyMode.protective if self.policy.protective_mode else SafetyMode.transparent

    @property
    def caps(self) -> Caps:
        return Caps(
            max_preview_rows=self.limits.preview_rows,
            max_preview_payload_bytes=self.limits.preview_bytes,
            max_columns=self.limits.preview_columns,
        )

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # Manually override from environment variables
        if "MANTORA_STORAGE__BACKEND" in os.environ:
            self.storage.backend = StorageBackend(os.environ["MANTORA_STORAGE__BACKEND"])
        if "MANTORA_STORAGE__SQLITE__PATH" in os.environ:
            self.storage.sqlite_path = Path(os.environ["MANTORA_STORAGE__SQLITE__PATH"])
