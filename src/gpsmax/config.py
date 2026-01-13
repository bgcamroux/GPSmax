"""gpsmax.config

Small configuration loader for GPSmax.

Design goals:
- Keep scripts Unix-friendly: CLI flags override everything.
- Provide sensible defaults if no config exists.
- Allow per-machine config without committing personal paths:
    ~/.config/gpsmax/config.toml
- Allow repo-local config:
    <repo_root>/config/config.toml
- Allow environment variable overrides for automation.

Precedence (highest to lowest) for any given value:
1) CLI argument (handled by each script)
2) Environment variables (GPSMAX_*)
3) User config: ~/.config/gpsmax/config.toml
4) Repo config: <repo_root>/config/config.toml
5) Hard defaults (~/GPS/... paths)

This module uses Python's built-in tomllib on Python 3.11+, or `tomli` if installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _load_toml(path: Path) -> dict[str, Any]:
    """Parse TOML file at `path`, returning an empty dict if missing."""
    if not path.is_file():
        return {}
    try:
        try:
            import tomllib  # type: ignore
            return tomllib.loads(path.read_text(encoding="utf-8")) or {}
        except ModuleNotFoundError:
            import tomli  # type: ignore
            return tomli.loads(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        raise RuntimeError(f"Failed to parse TOML config: {path} ({e})") from e


def _deep_get(d: dict[str, Any], dotted_key: str) -> Any:
    cur: Any = d
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _as_path(v: Any) -> Optional[Path]:
    if v is None:
        return None
    if isinstance(v, Path):
        return v.expanduser()
    if isinstance(v, str):
        return Path(v).expanduser()
    return None


def _env_path(var: str) -> Optional[Path]:
    val = os.environ.get(var)
    return Path(val).expanduser() if val else None


def find_repo_root(start: Path) -> Optional[Path]:
    """Walk upward looking for a directory that appears to be the repo root.

    Heuristic: contains a 'config' directory.
    """
    start = start.resolve()
    for p in [start] + list(start.parents):
        if (p / "config").is_dir():
            return p
    return None


def default_runtime_root() -> Path:
    return Path.home() / "GPS"


@dataclass(frozen=True)
class GPSmaxPaths:
    runtime_root: Path
    raw_root: Path
    work_root: Path
    db_root: Path
    sqlite_path: Path


@dataclass(frozen=True)
class GPSmaxConfig:
    paths: GPSmaxPaths
    source: dict[str, str]  # where values came from (for debugging)


def load_config(
    repo_root: Optional[Path] = None,
    repo_config_path: Optional[Path] = None,
    user_config_path: Optional[Path] = None,
) -> GPSmaxConfig:
    """Load GPSmax configuration and return normalized, ready-to-use Paths."""
    if repo_root is None:
        repo_root = find_repo_root(Path(__file__).resolve())
    if repo_config_path is None and repo_root is not None:
        repo_config_path = repo_root / "config" / "config.toml"

    if user_config_path is None:
        user_config_path = Path.home() / ".config" / "gpsmax" / "config.toml"

    repo_cfg = _load_toml(repo_config_path) if repo_config_path else {}
    user_cfg = _load_toml(user_config_path) if user_config_path else {}

    # Hard defaults
    runtime_root = default_runtime_root()
    raw_root = runtime_root / "_raw"
    work_root = runtime_root / "_work"
    db_root = runtime_root / "_db"
    sqlite_path = db_root / "gps.sqlite"
    src = {
        "paths.runtime_root": "default",
        "paths.raw_root": "default",
        "paths.work_root": "default",
        "paths.db_root": "default",
        "db.sqlite_path": "default",
    }

    # Repo config (if present)
    for k in ["paths.runtime_root", "paths.raw_root", "paths.work_root", "paths.db_root", "db.sqlite_path"]:
        v = _as_path(_deep_get(repo_cfg, k))
        if v is None:
            continue
        if k == "paths.runtime_root":
            runtime_root = v
        elif k == "paths.raw_root":
            raw_root = v
        elif k == "paths.work_root":
            work_root = v
        elif k == "paths.db_root":
            db_root = v
        elif k == "db.sqlite_path":
            sqlite_path = v
        src[k] = f"repo:{repo_config_path}"

    # User config (if present)
    for k in ["paths.runtime_root", "paths.raw_root", "paths.work_root", "paths.db_root", "db.sqlite_path"]:
        v = _as_path(_deep_get(user_cfg, k))
        if v is None:
            continue
        if k == "paths.runtime_root":
            runtime_root = v
        elif k == "paths.raw_root":
            raw_root = v
        elif k == "paths.work_root":
            work_root = v
        elif k == "paths.db_root":
            db_root = v
        elif k == "db.sqlite_path":
            sqlite_path = v
        src[k] = f"user:{user_config_path}"

    # Environment overrides
    env_map = {
        "GPSMAX_RUNTIME_ROOT": "paths.runtime_root",
        "GPSMAX_RAW_ROOT": "paths.raw_root",
        "GPSMAX_WORK_ROOT": "paths.work_root",
        "GPSMAX_DB_ROOT": "paths.db_root",
        "GPSMAX_SQLITE_PATH": "db.sqlite_path",
    }
    for env, key in env_map.items():
        v = _env_path(env)
        if v is None:
            continue
        if key == "paths.runtime_root":
            runtime_root = v
        elif key == "paths.raw_root":
            raw_root = v
        elif key == "paths.work_root":
            work_root = v
        elif key == "paths.db_root":
            db_root = v
        elif key == "db.sqlite_path":
            sqlite_path = v
        src[key] = f"env:{env}"

    # Derive standard subfolders if only runtime_root was set
    if src.get("paths.raw_root") == "default":
        raw_root = runtime_root / "_raw"
    if src.get("paths.work_root") == "default":
        work_root = runtime_root / "_work"
    if src.get("paths.db_root") == "default":
        db_root = runtime_root / "_db"
    if src.get("db.sqlite_path") == "default":
        sqlite_path = db_root / "gps.sqlite"

    paths = GPSmaxPaths(
        runtime_root=runtime_root.expanduser(),
        raw_root=raw_root.expanduser(),
        work_root=work_root.expanduser(),
        db_root=db_root.expanduser(),
        sqlite_path=sqlite_path.expanduser(),
    )
    return GPSmaxConfig(paths=paths, source=src)
