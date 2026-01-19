from __future__ import annotations

import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from mantora.models.events import ConfigSource, SessionContext
from mantora.policy.truncation import cap_text

_GIT_TIMEOUT_S: Final[float] = 2.0
_REPO_NAME_CAP_BYTES: Final[int] = 200
_BRANCH_CAP_BYTES: Final[int] = 200
_COMMIT_CAP_BYTES: Final[int] = 40
_TAG_CAP_BYTES: Final[int] = 200
_REPO_ROOT_CAP_BYTES: Final[int] = 500


@dataclass(frozen=True)
class ResolvedProjectRoot:
    path: Path
    source: ConfigSource
    tag: str | None


class ContextResolver:
    """Resolve git context for a session.

    Constraints:
    - Must not block startup (hard timeout per git subprocess).
    - Best-effort: missing git/tools should not raise.
    - Hard-cap anything persisted/exported.
    """

    def resolve(
        self,
        *,
        project_root: Path | None = None,
        hint_paths: list[Path] | None = None,
        forced_source: ConfigSource | None = None,
    ) -> SessionContext | None:
        resolved = self._resolve_project_root(project_root, hint_paths=hint_paths)
        if resolved is None:
            return None

        repo_root = resolved.path

        repo_name = repo_root.name
        repo_name, _ = cap_text(repo_name, max_bytes=_REPO_NAME_CAP_BYTES)

        branch = self._run_git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
        if branch is not None:
            branch, _ = cap_text(branch, max_bytes=_BRANCH_CAP_BYTES)

        commit = self._run_git(repo_root, "rev-parse", "HEAD")
        if commit is not None:
            commit, _ = cap_text(commit, max_bytes=_COMMIT_CAP_BYTES)

        dirty: bool | None = None
        status = self._run_git(repo_root, "status", "--porcelain", allow_empty=True)
        if status is not None:
            dirty = bool(status.strip())

        repo_root_str, _ = cap_text(str(repo_root), max_bytes=_REPO_ROOT_CAP_BYTES)

        tag: str | None = None
        if resolved.tag is not None:
            tag, _ = cap_text(resolved.tag, max_bytes=_TAG_CAP_BYTES)

        return SessionContext(
            repo_root=repo_root_str,
            repo_name=repo_name,
            branch=branch,
            commit=commit,
            dirty=dirty,
            config_source=forced_source or resolved.source,
            tag=tag,
        )

    def _resolve_project_root(
        self, project_root: Path | None, *, hint_paths: list[Path] | None
    ) -> ResolvedProjectRoot | None:
        if project_root is not None:
            root = self._discover_git_root(project_root)
            if root is None:
                return None
            return ResolvedProjectRoot(path=root, source="cli", tag=None)

        env_root = os.environ.get("MANTORA_PROJECT_ROOT")
        if env_root:
            root = self._discover_git_root(Path(env_root))
            if root is None:
                return None
            return ResolvedProjectRoot(path=root, source="env", tag=None)

        pinned = self._read_pinned_config(Path.cwd())
        if pinned is not None:
            root = self._discover_git_root(pinned.path)
            if root is None:
                return None
            return ResolvedProjectRoot(path=root, source="pinned", tag=pinned.tag)

        root = self._discover_git_root(Path.cwd())
        if root is None:
            if hint_paths:
                for hint in hint_paths:
                    hinted_root = self._discover_git_root(hint)
                    if hinted_root is not None:
                        return ResolvedProjectRoot(path=hinted_root, source="git", tag=None)
            return None
        return ResolvedProjectRoot(path=root, source="git", tag=None)

    def _discover_git_root(self, start: Path) -> Path | None:
        path = start.resolve()
        if path.is_file():
            path = path.parent

        for candidate in (path, *path.parents):
            if (candidate / ".git").exists():
                return candidate
        return None

    def _read_pinned_config(self, start: Path) -> ResolvedProjectRoot | None:
        """Read `.mantora.toml` from current dir parents, if present."""
        path = start.resolve()
        for candidate in (path, *path.parents):
            cfg_path = candidate / ".mantora.toml"
            if not cfg_path.exists():
                continue
            try:
                data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                return None

            raw_root = data.get("project_root")
            if not isinstance(raw_root, str) or not raw_root.strip():
                return None

            root = Path(raw_root)
            if not root.is_absolute():
                root = cfg_path.parent / root

            raw_tag = data.get("tag")
            tag = raw_tag if isinstance(raw_tag, str) and raw_tag.strip() else None
            return ResolvedProjectRoot(path=root, source="pinned", tag=tag)
        return None

    def _run_git(self, repo_root: Path, *args: str, allow_empty: bool = False) -> str | None:
        try:
            completed = subprocess.run(
                ["git", "-C", str(repo_root), *args],
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT_S,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

        if completed.returncode != 0:
            return None

        out = completed.stdout.strip()
        if out:
            return out
        return "" if allow_empty else None
