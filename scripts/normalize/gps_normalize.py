#!/usr/bin/env python3
"""
gps_normalize.py — GPSmax Phase B: Normalization

Purpose
-------
Normalize GPX files ingested into the GPSmax runtime tree (typically ~/GPS/_raw)
into a working tree (typically ~/GPS/_work), producing:
- a normalized GPX (pretty-printed, consistent naming)
- a sidecar JSON describing human intent + processing decisions
- a normalization manifest JSON listing produced artifacts + hashes

Design principles
-----------------
- Never modify _raw/ (treat as immutable)
- Deterministic output when run non-interactively
- Unix-friendly: supports both CLI args and fzf-driven selection
- Configurable paths via gpsmax.config (CLI > env > user config > repo config > defaults)

Notes
-----
- This script intentionally does not write to SQLite yet. We'll add a separate importer
  once the normalization outputs and sidecar schema stabilize.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Tuple
import xml.etree.ElementTree as ET

# ----------------------------
# GPSmax configuration import
# ----------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]  # <repo>/scripts/normalize/gps_normalize.py
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from gpsmax.config import load_config
except Exception:
    load_config = None  # type: ignore


SCRIPT_VERSION = "0.1.0"


# ----------------------------
# Errors
# ----------------------------
class NormalizeError(RuntimeError):
    pass


class FzfNotFoundError(NormalizeError):
    pass


# ----------------------------
# Small helpers
# ----------------------------
def log(msg: str) -> None:
    ts = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"{ts}  {msg}")


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]+", "", s)
    s = re.sub(r"[\s_-]+", "_", s).strip("_")
    return s or "track"


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def which(cmd: str) -> Optional[str]:
    from shutil import which as _which
    return _which(cmd)


# ----------------------------
# GPX parsing / writing
# ----------------------------
def _gpx_ns(root: ET.Element) -> str:
    """Return '{namespace}' prefix for default GPX namespace, or '' if none."""
    if root.tag.startswith("{") and "}" in root.tag:
        return root.tag.split("}", 1)[0] + "}"
    return ""


def first_time_utc_from_gpx(root: ET.Element) -> Optional[dt.datetime]:
    """Try to extract a representative UTC timestamp from GPX."""
    ns = _gpx_ns(root)

    # Prefer <metadata><time>
    md_time = root.find(f"{ns}metadata/{ns}time")
    if md_time is not None and (md_time.text or "").strip():
        t = (md_time.text or "").strip()
        try:
            return dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
        except Exception:
            pass

    # Else first trkpt time
    trkpt_time = root.find(f".//{ns}trkpt/{ns}time")
    if trkpt_time is not None and (trkpt_time.text or "").strip():
        t = (trkpt_time.text or "").strip()
        try:
            return dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
        except Exception:
            pass

    return None


def _indent(elem: ET.Element, level: int = 0) -> None:
    """
    In-place pretty-printer for ElementTree that avoids the "double blank line" issue.
    """
    i = "\n" + ("  " * level)
    if len(elem):
        if not (elem.text or "").strip():
            elem.text = i + "  "
        for child in elem:
            _indent(child, level + 1)
        if not (elem.tail or "").strip():
            elem.tail = i
    else:
        if level and not (elem.tail or "").strip():
            elem.tail = i


def normalize_gpx(src: Path, title: str) -> Tuple[bytes, dict]:
    """
    Normalize a GPX file (formatting + consistent naming).

    Returns:
      - normalized GPX bytes (utf-8, with xml declaration)
      - stats dict (for sidecar/manifest)
    """
    raw = src.read_bytes()
    try:
        root = ET.fromstring(raw)
    except Exception as e:
        raise NormalizeError(f"Failed to parse GPX: {src} ({e})") from e

    ns = _gpx_ns(root)

    # Ensure <metadata> exists
    metadata = root.find(f"{ns}metadata")
    if metadata is None:
        metadata = ET.Element(f"{ns}metadata")
        if list(root):
            root.insert(0, metadata)
        else:
            root.append(metadata)

    # Ensure <metadata><name> exists and matches title
    md_name = metadata.find(f"{ns}name")
    if md_name is None:
        md_name = ET.SubElement(metadata, f"{ns}name")
    md_name.text = title

    # Ensure <trk><name> exists and matches title (first track only)
    trk = root.find(f"{ns}trk")
    if trk is not None:
        trk_name = trk.find(f"{ns}name")
        if trk_name is None:
            trk_name = ET.SubElement(trk, f"{ns}name")
        trk_name.text = title

    # Pretty print without blank lines
    _indent(root)

    out_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    t0 = first_time_utc_from_gpx(root)
    stats = {
        "source_bytes": len(raw),
        "normalized_bytes": len(out_bytes),
        "first_time_utc": t0.isoformat() if t0 else None,
        "title": title,
    }
    return out_bytes, stats


# ----------------------------
# fzf selection
# ----------------------------
def list_gpx_candidates(raw_root: Path) -> list[Path]:
    if not raw_root.is_dir():
        return []
    out: list[Path] = []
    for p in raw_root.rglob("*.gpx"):
        if p.is_file():
            out.append(p)
    out.sort()
    return out


def fzf_select(paths: list[Path], root: Path, multi: bool = True) -> list[Path]:
    if not which("fzf"):
        raise FzfNotFoundError("fzf not found on PATH. Install fzf or pass GPX files explicitly.")

    rels = [str(p.relative_to(root)) if p.is_relative_to(root) else str(p) for p in paths]
    input_text = "\n".join(rels)

    cmd = ["fzf"]
    if multi:
        cmd.append("-m")
    cmd += [
        "--prompt", "GPSmax normalize > ",
        "--height", "80%",
        "--layout", "reverse",
        "--border",
        "--preview", f"head -n 60 '{root}/{{}}' 2>/dev/null || true",
        "--preview-window", "right:60%:wrap",
    ]

    proc = subprocess.run(
        cmd,
        input=input_text.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode not in (0, 130):
        raise NormalizeError(f"fzf failed: {proc.stderr.decode('utf-8', errors='replace')}")
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    if not out:
        return []
    selected: list[Path] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        selected.append((root / line).resolve() if not Path(line).is_absolute() else Path(line).resolve())
    return selected


# ----------------------------
# Sidecar + manifest
# ----------------------------
@dataclass
class NormalizedArtifact:
    source_path: str
    source_sha256: str
    normalized_path: str
    normalized_sha256: str
    sidecar_path: str
    title: str
    activity: str
    geotag_candidate: bool
    photos_pending: bool
    normalized_utc: str


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sidecar_doc(art: NormalizedArtifact, gpx_stats: dict, notes: str) -> dict:
    return {
        "schema": "gpsmax.sidecar.v1",
        "created_utc": art.normalized_utc,
        "tool": {"name": "gps_normalize.py", "version": SCRIPT_VERSION},
        "source": {"path": art.source_path, "sha256": art.source_sha256},
        "output": {"normalized_gpx": art.normalized_path, "sha256": art.normalized_sha256},
        "title": art.title,
        "activity": art.activity,
        "geotag": {"candidate": art.geotag_candidate, "photos_pending": art.photos_pending},
        "gpx_stats": gpx_stats,
        "notes": notes,
        "decisions": {"set_metadata_name": True, "set_trk_name": True, "pretty_print": True},
    }


def normalization_manifest(arts: list[NormalizedArtifact], run: dict) -> dict:
    by_activity: dict[str, int] = {}
    for a in arts:
        by_activity[a.activity] = by_activity.get(a.activity, 0) + 1
    return {
        "schema": "gpsmax.normalization_manifest.v1",
        "run": run,
        "counts": {
            "tracks": len(arts),
            "by_activity": by_activity,
            "geotag_candidates": sum(1 for a in arts if a.geotag_candidate),
        },
        "artifacts": [asdict(a) for a in arts],
    }


# ----------------------------
# User prompting
# ----------------------------
def prompt_bool(prompt: str, default: bool) -> bool:
    d = "Y/n" if default else "y/N"
    while True:
        ans = input(f"{prompt} [{d}]: ").strip().lower()
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False


def prompt_str(prompt: str, default: str = "") -> str:
    if default:
        ans = input(f"{prompt} [{default}]: ").strip()
        return ans if ans else default
    return input(f"{prompt}: ").strip()


# ----------------------------
# Main
# ----------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="GPSmax Phase B: normalize GPX files into _work + sidecars.")
    ap.add_argument("gpx", nargs="*", help="One or more GPX files (from _raw). If omitted, use fzf selection.")
    ap.add_argument("--raw-root", default=None, help="Raw root (default: from GPSmax config or ~/GPS/_raw)")
    ap.add_argument("--work-root", default=None, help="Work root (default: from GPSmax config or ~/GPS/_work)")
    ap.add_argument("--device-id", default=None, help="Override device_id directory name (default: infer from path if possible)")
    ap.add_argument("--activity", default=None, help="Activity label (e.g., hiking, driving, cycling).")
    ap.add_argument("--title", default=None, help="Track title.")
    ap.add_argument("--geotag", action="store_true", help="Mark as geotag candidate (photos were taken and may be geotagged).")
    ap.add_argument("--no-geotag", action="store_true", help="Explicitly mark as not a geotag candidate.")
    ap.add_argument("--photos-pending", action="store_true", help="If geotag, mark photos_pending=true (default true when geotag candidate).")
    ap.add_argument("--notes", default=None, help="Notes to add to sidecar.")
    ap.add_argument("--prompt", action="store_true", help="Prompt for title/activity/geotag per file.")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be done but do not write files.")
    ap.add_argument("--verbose", action="store_true", help="More logging.")
    args = ap.parse_args()

    # Resolve roots (CLI > config > defaults)
    if args.raw_root:
        raw_root = Path(args.raw_root).expanduser()
    else:
        raw_root = load_config().paths.raw_root if load_config is not None else (Path.home() / "GPS" / "_raw")

    if args.work_root:
        work_root = Path(args.work_root).expanduser()
    else:
        work_root = load_config().paths.work_root if load_config is not None else (Path.home() / "GPS" / "_work")

    raw_root = raw_root.expanduser()
    work_root = work_root.expanduser()

    # Determine selected inputs
    if args.gpx:
        selected = [Path(p).expanduser().resolve() for p in args.gpx]
    else:
        candidates = list_gpx_candidates(raw_root)
        if not candidates:
            log(f"No GPX candidates found under raw_root={raw_root}")
            return 2
        selected = fzf_select(candidates, raw_root, multi=True)
        if not selected:
            log("No selection made. Exiting.")
            return 0

    arts: list[NormalizedArtifact] = []
    run_id = utc_now_iso()
    run = {
        "run_id": run_id,
        "started_utc": run_id,
        "raw_root": str(raw_root),
        "work_root": str(work_root),
        "script_version": SCRIPT_VERSION,
    }

    for src in selected:
        if not src.is_file():
            log(f"Skip non-file: {src}")
            continue

        # Infer device_id from path: .../_raw/<YYYY>/<YYYY-MM-DD>/<device_id>/...
        device_id = args.device_id
        if device_id is None:
            try:
                rel = src.relative_to(raw_root)
                parts = rel.parts
                if len(parts) >= 3:
                    device_id = parts[2]
            except Exception:
                device_id = "unknown"
        device_id = device_id or "unknown"

        # Determine date from GPX, else today
        try:
            root = ET.fromstring(src.read_bytes())
            t0 = first_time_utc_from_gpx(root)
        except Exception:
            t0 = None
        if t0:
            y = f"{t0.year:04d}"
            day = t0.date().isoformat()
        else:
            now = dt.datetime.now().astimezone()
            y = f"{now.year:04d}"
            day = now.date().isoformat()

        default_title = args.title or src.stem
        default_activity = args.activity or "unknown"

        if args.prompt:
            title = prompt_str(f"Title for {src.name}", default=default_title)
            activity = prompt_str(f"Activity for {src.name}", default=default_activity) or default_activity
            geotag_default = True if args.geotag and not args.no_geotag else False
            geotag_candidate = prompt_bool(f"Geotag candidate for {src.name}?", default=geotag_default)
            notes = prompt_str(f"Notes for {src.name}", default=(args.notes or ""))
        else:
            title = default_title
            activity = default_activity
            if args.no_geotag:
                geotag_candidate = False
            elif args.geotag:
                geotag_candidate = True
            else:
                geotag_candidate = False
            notes = args.notes or ""

        photos_pending = True if geotag_candidate else False
        if geotag_candidate and args.photos_pending:
            photos_pending = True

        track_slug = slugify(title)
        out_dir = work_root / y / day / device_id / track_slug
        normalized_path = out_dir / f"{track_slug}.gpx"
        sidecar_path = out_dir / f"{track_slug}.sidecar.json"

        if args.verbose or args.dry_run:
            log(f"Plan: {src} -> {normalized_path}")
            log(f"      sidecar -> {sidecar_path}")

        if args.dry_run:
            continue

        ensure_dir(out_dir)

        norm_bytes, stats = normalize_gpx(src, title=title)
        normalized_path.write_bytes(norm_bytes)

        src_hash = sha256_file(src)
        norm_hash = sha256_file(normalized_path)

        art = NormalizedArtifact(
            source_path=str(src),
            source_sha256=src_hash,
            normalized_path=str(normalized_path),
            normalized_sha256=norm_hash,
            sidecar_path=str(sidecar_path),
            title=title,
            activity=activity,
            geotag_candidate=geotag_candidate,
            photos_pending=photos_pending,
            normalized_utc=utc_now_iso(),
        )

        write_json(sidecar_path, sidecar_doc(art, stats, notes=notes))
        arts.append(art)
        log(f"Normalized: {src.name} -> {normalized_path.name}")

    if not args.dry_run:
        run_manifest_dir = work_root / "manifests"
        ensure_dir(run_manifest_dir)
        manifest_path = run_manifest_dir / f"normalize_{run_id.replace(':','').replace('+','_')}.json"
        write_json(manifest_path, normalization_manifest(arts, run))
        log(f"Wrote normalization manifest: {manifest_path}")

    if not arts and not args.dry_run:
        log("No files normalized.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
