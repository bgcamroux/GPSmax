# gpsmax/scripts/util/paths.py
from __future__ import annotations

import re
from pathlib import Path
from shutil import which as _which

_slug_bad = re.compile(r"[^a-z0-9]+")

def ensure_dir(path: Path) -> None:
    """Ensure a directory exists."""
    path.mkdir(parents=True, exist_ok=True)

def slugify(text: str, *, default: str = "untitled") -> str:
    """Create a path-safe slug (lowercase, a-z0-9 and single underscores)."""
    s = (text or "").strip().lower()
    s = _slug_bad.sub("_", s).strip("_")
    return s or default

def which(cmd: str) -> Optional[str]:
    return _which(cmd)
