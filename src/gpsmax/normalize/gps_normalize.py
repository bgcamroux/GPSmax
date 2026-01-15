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
import json
import re
import subprocess
import sys
import shlex
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from gpsmax.util.logging import log, utc_now_iso
from gpsmax.util.hashing import sha256_file
#from gpsmax.util.subprocess import run_cmd as run
from gpsmax.util.paths import ensure_dir, slugify, which
from gpsmax.formats.gpx import first_time_utc_from_gpx, read_gpx, normalize_gpx
from gpsmax.util.fzf import fzf_select_paths
from gpsmax.errors import FzfNotFoundError, NormalizeError

# ----------------------------
# GPSmax configuration import
# ----------------------------
try:
    from gpsmax.config import load_config
except Exception:
    load_config = None  # type: ignore


SCRIPT_VERSION = "0.1.0"


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

#    rels = [str(p.relative_to(root)) if p.is_relative_to(root) else str(p) for p in paths]
    lines = [f"{p.name}\t{p}" for p in paths]
    input_text = "\n".join(lines) + "\n"
    PREVIEW_PY = r"""
    import sys
    import xml.etree.ElementTree as ET

    p = sys.argv[1]
    ns = {"g": "http://www.topografix.com/GPX/1/1"}

    def txt(el, path, default=""):
        if el is None:
            return default
        return el.findtext(path, default=default, namespaces=ns)

    def show_waypoints(root):
        wpts = root.findall("g:wpt", ns)
        print(f"Waypoints: {len(wpts)}\n")
        for w in wpts[:20]:
            lat = w.get("lat", "")
            lon = w.get("lon", "")
            name = txt(w, "g:name", default="(no name)")
            desc = txt(w, "g:desc", default="")
            t = txt(w, "g:time", default="")
            line = f"{name}  ({lat}, {lon})"
            if t:
                line += f"  {t}"
            print(line)
            if desc:
                print(f"  {desc}")

    def show_routes(root):
        rtes = root.findall("g:rte", ns)
        print(f"Routes: {len(rtes)}\n")
        r = rtes[0]
        rname = txt(r, "g:name", default="(no rte name)")
        print(f"Route: {rname}\n")
        pts = r.findall("g:rtept", ns)
        print(f"Routepoints: {len(pts)}\n")
        for pt in pts[:12]:
            lat = pt.get("lat", "")
            lon = pt.get("lon", "")
            t = txt(pt, "g:time", default="")
            nm = txt(pt, "g:name", default="")
            extra = f"  {nm}" if nm else ""
            if t:
                print(f"{lat}, {lon}  {t}{extra}")
            else:
                print(f"{lat}, {lon}{extra}")

    def show_tracks(root):
        trks = root.findall("g:trk", ns)
        print(f"Tracks: {len(trks)}\n")
        trk = trks[0]
        name = txt(trk, "g:name", default="(no trk name)")
        print(f"Track: {name}\n")
        pts = trk.findall(".//g:trkpt", ns)
        print(f"Trackpoints: {len(pts)}\n")
        for pt in pts[:12]:
            lat = pt.get("lat", "")
            lon = pt.get("lon", "")
            t = txt(pt, "g:time", default="")
            if t:
                print(f"{lat}, {lon}  {t}")
            else:
                print(f"{lat}, {lon}")

    try:
        tree = ET.parse(p)
        root = tree.getroot()
    except Exception as e:
        print(f"Failed to parse GPX: {e}")
        raise SystemExit(0)

    # Prefer tracks, then routes, then waypoints
    if root.find("g:trk", ns) is not None:
        show_tracks(root)
    elif root.find("g:rte", ns) is not None:
        show_routes(root)
    elif root.find("g:wpt", ns) is not None:
        show_waypoints(root)
    else:
        print("No <trk>, <rte>, or <wpt> elements found.")
    """

    fzf_cmd = ["fzf",
           "--ansi",
           "--delimiter=\t",
           "--header", "Select GPX file(s):",
           "--height", "60%",
           "--layout", "reverse",
           "--border",
           "--multi" if multi else "--no-multi",
           "--nth=1", "--with-nth=1",
           "--preview", f"python -c {shlex.quote(PREVIEW_PY)} {{2}}",
           "--preview-window", "right:60%:wrap",
           ]
    
    proc = subprocess.run(
        fzf_cmd,
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

        # fzf returns whole displayed line: "name<TAB>fullpath"
        if "\t" in line:
            _, path_str = line.split("\t",1)
        else:
            path_str = line
            
        p = Path(path_str).expanduser()
        selected.append(p.resolve())
        
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


def render_name_template(template: str, *, date: str, title: str, activity: str, device: str) -> str:
    """
    Render a name template using a controlled set of variables.

    Supported placeholders:
      {date}     e.g., 2025-08-25
      {title}    human title
      {activity} activity label
      {device}   device_id (e.g., gpsmap67)

    We fail fast with a clear message if the template references an unknown key.
    """
    try:
        return template.format(date=date, title=title, activity=activity, device=device)
    except KeyError as e:
        raise NormalizeError(
            f"Unknown placeholder {e!s} in name_template: {template!r}. "
            "Valid: {date}, {title}, {activity}, {device}."
        ) from e


def sanitize_filename(s: str) -> str:
    """
    Make a string safe-ish for a filename without full slugification.

    This is only used if you later decide to allow non-slugified names.
    For now, keep slugify() for everything.
    """
    s = s.strip()
    s = re.sub(r"[^\w.\-]+", "_", s, flags=re.UNICODE)  # spaces/punctuation to underscore
    s = re.sub(r"_+", "_", s)                           # collapse repeats
    s = s.strip("._-")
    return s or "track"


def choose_output_slug(base_slug: str, out_base: Path, src: Path) -> str:
    """
    Choose a directory slug under out_base that will not clobber an existing track.

    - If out_base/base_slug does not exist: use it.
    - If it exists: append a deterministic suffix derived from src content.
    """
    candidate = base_slug
    target_dir = out_base / candidate
    if not target_dir.exists():
        return candidate

    full_hash = sha256_file(src)
    sid8 = full_hash[:8]
    sid12 = full_hash[:12]
    candidate = f"{base_slug}__{sid8}"
    target_dir = out_base / candidate
    if not target_dir.exists():
        return candidate

    # Extremely unlikely: collision on both base slug and suffix.
    # Fall back to widening the suffix.
    return f"{base_slug}__{sid12}"


# ----------------------------
# Main
# ----------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="GPSmax Phase 2: Normalize GPX files into _work + sidecars.")
    ap.add_argument("gpx", nargs="*", help="One or more GPX files (from _raw). If omitted, use fzf selection.")
    ap.add_argument("--raw-root", default=None, help="Raw root (default: from GPSmax config or ~/GPS/_raw)")
    ap.add_argument("--work-root", default=None, help="Work root (default: from GPSmax config or ~/GPS/_work)")
    ap.add_argument("--device-id", default=None, help="Override device_id directory name (default: infer from path if possible)")
    ap.add_argument("--preset", default=None, help="Normalization preset name (from config.toml).")
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
    cfg = load_config() if load_config is not None else None
    norm_cfg = cfg.normalize if cfg else None
    if args.verbose and preset:
        log(f"Using normalization preset: {args.preset or norm_cfg.default_preset}")
    
    preset = None
    if norm_cfg:
        preset = norm_cfg.get_preset(args.preset)
        
    if args.raw_root:
        raw_root = Path(args.raw_root).expanduser()
    else:
        raw_root = cfg.paths.raw_root if cfg else (Path.home() / "GPS" / "_raw")

    if args.work_root:
        work_root = Path(args.work_root).expanduser()
    else:
        work_root = cfg.paths.work_root if cfg else (Path.home() / "GPS" / "_work")

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
            log(f"'{src}' is not a file: Skipping")
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
            tree = read_gpx(src)
            root = tree.getroot()
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
        
        default_activity = (
            args.activity
            if args.activity is not None
            else (preset.activity if preset else "unknown")
        )

        do_prompt = args.prompt or (norm_cfg and not norm_cfg.prompt_only_missing)
        if do_prompt:
            title = prompt_str(f"Title for {src.name}", default=default_title)
            activity = prompt_str(f"Activity for {src.name}", default=default_activity) or default_activity
            if args.no_geotag:
                geotag_default = False
            elif args.geotag:
                geotag_default = True
            else:
                geotag_default = preset.geotag_candidate if preset else False
            geotag_candidate = prompt_bool(f"Geotag candidate for {src.name}?", default=geotag_default)
            notes = prompt_str(f"Notes for {src.name}", default=(args.notes or ""))
        else:
            title = default_title
            activity = default_activity
            if args.no_geotag:
                geotag_candidate = preset.geotag_candidate if preset else False
            elif args.geotag:
                geotag_candidate = True
            else:
                geotag_candidate = False
            notes = args.notes or ""

        photos_pending = True if geotag_candidate else False
        if geotag_candidate and args.photos_pending:
            photos_pending = True

        # 1. Choose template: CLI may override later if added, but for now
        #    we take it from the preset/config.
        template = preset.name_template if preset else "{date}_{title}"

        # 2. Render human-readable base name
        #    May contain spaces, punctuation, etc.
        base_name = render_name_template(
            template,
            date=day,         # YYYY-MM-DD from GPX or local date fallback
            title=title,
            activity=activity,
            device=device_id,
        )

        # 3. Convert to path-safe name for dir & output filenames.
        #    For now we slugify the final name as it is stable and consistent
        track_slug = slugify(base_name)
        out_base = work_root / y / day / device_id
        track_slug = choose_output_slug(track_slug, out_base, src)

        out_dir = out_base / track_slug
        normalized_path = out_dir / f"{track_slug}.gpx"
        sidecar_path = out_dir / f"{track_slug}.sidecar.json"
        
        if args.verbose or args.dry_run:
            log(f"Plan: {src} -> {normalized_path}")
            log(f"      sidecar -> {sidecar_path}")

        if args.dry_run:
            continue

        ensure_dir(out_dir)

        res = normalize_gpx(
            in_path = src, out_path = normalized_path, track_name = title,
            set_metadata_name = True, set_trk_name = True,
            ensure_metadata_time = True, pretty = True,
        )

        # Convert NormalizeResult -> dict for sidecar
        stats = asdict(res)

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
        log(f"Normalized: {src.name} -> {normalized_path.name}\n")

    # Write the manifest UNLESS it is a dry-run
    if not args.dry_run:
        run_manifest_dir = work_root / "manifests"
        ensure_dir(run_manifest_dir)
        run_id_slug = run_id.replace(":", "").replace("+", "_").replace("-", "").replace(".", "")
        manifest_path = run_manifest_dir / f"normalize_{run_id_slug}.json"
        write_json(manifest_path, normalization_manifest(arts, run))
        log(f"Wrote normalization manifest: {manifest_path}")

    if not arts and not args.dry_run:
        log("No files normalized.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
