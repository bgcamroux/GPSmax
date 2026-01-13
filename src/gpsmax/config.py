"""
GPSmax configuration loader

This module centralizes *all* configuration handling for GPSmax.

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

IMPORTANT PHILOSOPHY NOTE:
--------------------------
This file is intentionally verbose and explicit. Configuration code tends to
become "write once, fear forever" unless it is carefully documented.

Future-you should be able to open this file and understand:
- where values come from
- why precedence works the way it does
- where to safely add new config sections
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# TOML loading helpers
# ---------------------------------------------------------------------------
def _load_toml(path: Path) -> dict[str, Any]:
    """
    Parse a TOML file at `path`.

    Behavior:
    - If the file does not exist, return an empty dict (non-fatal).
    - If the file exists but is invalid TOML, raise a RuntimeError
      with a clear, user-facing message.

    Rationale:
    - Missing config files are normal and expected.
    - Malformed config files indicate user intent and should fail loudly.
    """
    if not path.is_file():
        return {}

    try:
        try:
            # Python 3.11+ standard library
            import tomllib
            return tomllib.loads(path.read_text(encoding="utf-8")) or {}
        except ModuleNotFoundError:
            # Back-compat path if ever needed
            import tomli
            return tomli.loads(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        # Wrap parsing errors with file context for usability
        raise RuntimeError(f"Failed to parse TOML config: {path} ({e})") from e


# ---------------------------------------------------------------------------
# Generic coercion helpers
# ---------------------------------------------------------------------------
def _deep_get(d: dict[str, Any], dotted_key: str) -> Any:
    """
    Fetch nested dictionary values using dot-separated keys.

    Example:
        _deep_get(cfg, "paths.runtime_root")

    Returns None if any part of the path is missing.

    Rationale:
    - Keeps config lookup logic compact
    - Avoids KeyError pyramids
    """
    cur: Any = d
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _as_path(v: Any) -> Optional[Path]:
    """
    Coerce a config value into a pathlib.Path if possible.

    Accepted inputs:
    - Path (expanded)
    - string (expanded via ~)

    Returns None if value cannot be interpreted as a path.
    """
    if v is None:
        return None
    if isinstance(v, Path):
        return v.expanduser()
    if isinstance(v, str):
        return Path(v).expanduser()
    return None


def _as_bool(v: Any, default: bool) -> bool:
    """
    Coerce loosely-typed config values into booleans.

    Accepts common truthy / falsy representations so that:
    - TOML
    - environment variables
    - user overrides

    all behave consistently.
    """
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "y", "1", "on"):
            return True
        if s in ("false", "no", "n", "0", "off"):
            return False
    return default


def _as_str(v: Any, default: str) -> str:
    """
    Coerce config values into strings.

    Always returns a string; never raises.
    """
    if v is None:
        return default
    return str(v)


def _env_path(var: str) -> Optional[Path]:
    """
    Read an environment variable and interpret it as a Path.

    Used for automation, CI, and power-user overrides.
    """
    val = os.environ.get(var)
    return Path(val).expanduser() if val else None


# ---------------------------------------------------------------------------
# Normalization config parsing (raw TOML -> typed objects)
# ---------------------------------------------------------------------------
def _parse_normalize_section(cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Extract normalization settings and preset blocks from raw TOML.

    Input:
        Raw TOML dictionary (repo or user config)

    Output:
        (settings_dict, presets_dict)

    Where:
    - settings_dict contains global normalize behavior flags
    - presets_dict maps preset_name -> raw preset dict

    Rationale:
    - Keeps TOML parsing separate from typed config construction
    - Allows repo and user configs to be merged cleanly
    """
    norm = cfg.get("normalize", {}) or {}

    # High-level normalize behavior flags
    settings = {
        "default_preset": _as_str(norm.get("default_preset"), "default"),
        "prompt_only_missing": _as_bool(norm.get("prompt_only_missing"), True),
        "write_sidecar": _as_bool(norm.get("write_sidecar"), True),
    }

    # Presets are free-form dicts at this stage
    presets = norm.get("presets", {}) or {}
    if not isinstance(presets, dict):
        presets = {}

    # Normalize keys to strings and values to dicts
    presets = {str(k): (v if isinstance(v, dict) else {}) for k, v in presets.items()}

    return settings, presets


# ---------------------------------------------------------------------------
# Repo discovery + defaults
# ---------------------------------------------------------------------------
def find_repo_root(start: Path) -> Optional[Path]:
    """
    Walk upward from `start` looking for the GPSmax repo root.

    Heuristic:
    - The presence of a `config/` directory marks the repo root

    This is intentionally simple and explicit.
    """
    start = start.resolve()
    for p in [start] + list(start.parents):
        if (p / "config").is_dir():
            return p
    return None


def default_runtime_root() -> Path:
    """
    Default runtime root if nothing is configured.

    All runtime data (_raw, _work, _db) derives from this path
    unless explicitly overridden.
    """
    return Path.home() / "GPS"


# ---------------------------------------------------------------------------
# Typed config dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NormalizePreset:
    """
    Defaults applied to per-file normalization.

    These values seed interactive prompts and
    non-interactive normalization runs.
    """

    activity: str = "unknown"
    geotag_candidate: bool = False
    name_template: str = "{date}_{title}_{activity}"
    slugify_title: bool = True
    title_from_filename_if_missing: bool = True


@dataclass(frozen=True)
class NormalizeConfig:
    """
    Parsed and merged normalization configuration.

    This object is what normalization code should consume.
    """

    default_preset: str = "default"
    prompt_only_missing: bool = True
    write_sidecar: bool = True
    presets: dict[str, NormalizePreset] = None

    def get_preset(self, name: Optional[str]) -> NormalizePreset:
        """
        Return the requested preset, falling back safely.

        Resolution order:
        1) Explicitly requested preset
        2) Configured default_preset
        3) Literal "default" preset
        4) Hard-coded NormalizePreset()
        """
        presets = self.presets or {}
        if name and name in presets:
            return presets[name]
        if self.default_preset in presets:
            return presets[self.default_preset]
        if "default" in presets:
            return presets["default"]
        return NormalizePreset()


@dataclass(frozen=True)
class GPSmaxPaths:
    """
    Canonical resolved filesystem paths used by GPSmax.
    """

    runtime_root: Path
    raw_root: Path
    work_root: Path
    db_root: Path
    sqlite_path: Path


@dataclass(frozen=True)
class GPSmaxConfig:
    """
    Fully merged GPSmax configuration.

    Attributes:
    - paths: resolved filesystem layout
    - normalize: normalization behavior + presets
    - source: provenance map showing where each value came from
    """

    paths: GPSmaxPaths
    normalize: NormalizeConfig
    source: dict[str, str]


# ---------------------------------------------------------------------------
# Main config loader
# ---------------------------------------------------------------------------
def load_config(
    repo_root: Optional[Path] = None,
    repo_config_path: Optional[Path] = None,
    user_config_path: Optional[Path] = None,
) -> GPSmaxConfig:
    """
    Load, merge, and normalize all GPSmax configuration.

    This function is the single authoritative entry point
    for configuration access.
    """

    # Locate repo and config files
    if repo_root is None:
        repo_root = find_repo_root(Path(__file__).resolve())
    if repo_config_path is None and repo_root is not None:
        repo_config_path = repo_root / "config" / "config.toml"
    if user_config_path is None:
        user_config_path = Path.home() / ".config" / "gpsmax" / "config.toml"

    # Load raw TOML dicts
    repo_cfg = _load_toml(repo_config_path) if repo_config_path else {}
    user_cfg = _load_toml(user_config_path) if user_config_path else {}

    # ------------------------------------------------------------------
    # Path defaults
    # ------------------------------------------------------------------
    runtime_root = default_runtime_root()
    raw_root = runtime_root / "_raw"
    work_root = runtime_root / "_work"
    db_root = runtime_root / "_db"
    sqlite_path = db_root / "gps.sqlite"

    # Track provenance for debugging and audits
    src = {
        "paths.runtime_root": "default",
        "paths.raw_root": "default",
        "paths.work_root": "default",
        "paths.db_root": "default",
        "db.sqlite_path": "default",
    }

    # ------------------------------------------------------------------
    # Normalization defaults
    # ------------------------------------------------------------------
    norm_default_preset = "default"
    norm_prompt_only_missing = True
    norm_write_sidecar = True
    norm_presets: dict[str, dict[str, Any]] = {}

    norm_src = {
        "normalize.default_preset": "default",
        "normalize.prompt_only_missing": "default",
        "normalize.write_sidecar": "default",
        "normalize.presets": "default",
    }

    # Apply repo normalization config
    repo_norm, repo_presets = _parse_normalize_section(repo_cfg)
    if repo_norm:
        norm_default_preset = repo_norm["default_preset"]
        norm_prompt_only_missing = repo_norm["prompt_only_missing"]
        norm_write_sidecar = repo_norm["write_sidecar"]
        norm_src["normalize.default_preset"] = f"repo:{repo_config_path}"
        norm_src["normalize.prompt_only_missing"] = f"repo:{repo_config_path}"
        norm_src["normalize.write_sidecar"] = f"repo:{repo_config_path}"

    if repo_presets:
        norm_presets.update(repo_presets)
        norm_src["normalize.presets"] = f"repo:{repo_config_path}"

    # Apply user normalization config (overrides repo)
    user_norm, user_presets = _parse_normalize_section(user_cfg)
    if user_norm:
        norm_default_preset = user_norm["default_preset"]
        norm_prompt_only_missing = user_norm["prompt_only_missing"]
        norm_write_sidecar = user_norm["write_sidecar"]
        norm_src["normalize.default_preset"] = f"user:{user_config_path}"
        norm_src["normalize.prompt_only_missing"] = f"user:{user_config_path}"
        norm_src["normalize.write_sidecar"] = f"user:{user_config_path}"

    if user_presets:
        norm_presets.update(user_presets)
        norm_src["normalize.presets"] = f"user:{user_config_path}"

    # Build typed presets
    typed_presets: dict[str, NormalizePreset] = {}
    for pname, block in norm_presets.items():
        typed_presets[pname] = NormalizePreset(
            activity=_as_str(block.get("activity"), "unknown"),
            geotag_candidate=_as_bool(block.get("geotag_candidate"), False),
            name_template=_as_str(block.get("name_template"), "{date}_{title}"),
            slugify_title=_as_bool(block.get("slugify_title"), True),
            title_from_filename_if_missing=_as_bool(
                block.get("title_from_filename_if_missing"), True
            ),
        )

    # Ensure a safe default always exists
    typed_presets.setdefault("default", NormalizePreset())

    normalize_cfg = NormalizeConfig(
        default_preset=norm_default_preset,
        prompt_only_missing=norm_prompt_only_missing,
        write_sidecar=norm_write_sidecar,
        presets=typed_presets,
    )

    src.update(norm_src)

    # ------------------------------------------------------------------
    # Repo + user path overrides
    # ------------------------------------------------------------------
    for cfg, label in ((repo_cfg, "repo"), (user_cfg, "user")):
        for k in [
            "paths.runtime_root",
            "paths.raw_root",
            "paths.work_root",
            "paths.db_root",
            "db.sqlite_path",
        ]:
            v = _as_path(_deep_get(cfg, k))
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
            src[k] = f"{label}:{repo_config_path if label == 'repo' else user_config_path}"

    # Environment variable overrides (highest non-CLI precedence)
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

    # Derive subfolders if runtime_root changed
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

    return GPSmaxConfig(paths=paths, normalize=normalize_cfg, source=src)
