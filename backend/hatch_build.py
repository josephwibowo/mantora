from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

try:
    from hatchling.builders.hooks.plugin import BuildHookInterface  # type: ignore
except ImportError:  # pragma: no cover - hatchling import path varies by version
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface  # type: ignore


def _copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


class CustomBuildHook(BuildHookInterface):  # type: ignore
    def initialize(self, _version: str, build_data: dict[str, Any]) -> None:
        root = Path(self.root)
        frontend_dist = root.parent / "frontend" / "dist"
        enforce_frontend = os.environ.get("MANTORA_ENFORCE_FRONTEND_DIST") == "1"

        src_pkg_root = root / "src" / "mantora"
        flat_pkg_root = root / "mantora"

        static_candidates = [src_pkg_root / "_static", flat_pkg_root / "_static"]
        demo_candidates = [src_pkg_root / "_demo", flat_pkg_root / "_demo"]

        static_target = (
            src_pkg_root / "_static" if src_pkg_root.exists() else flat_pkg_root / "_static"
        )
        if frontend_dist.is_dir():
            _copy_tree(frontend_dist, static_target)
        else:
            static_target = _first_existing(static_candidates) or static_target
            if enforce_frontend and not any(static_target.rglob("*")):
                raise RuntimeError(
                    "frontend/dist not found. Run `pnpm build` in frontend/ before packaging."
                )

        demo_target = src_pkg_root / "_demo" if src_pkg_root.exists() else flat_pkg_root / "_demo"
        demo_src = root.parent / "demo"
        if demo_src.is_dir():
            _copy_tree(demo_src, demo_target)
        else:
            demo_target = _first_existing(demo_candidates) or demo_target

        force_include = build_data.setdefault("force_include", {})
        if static_target.exists():
            force_include[str(static_target)] = "mantora/_static"
        if demo_target.exists():
            force_include[str(demo_target)] = "mantora/_demo"
