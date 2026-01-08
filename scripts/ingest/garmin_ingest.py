#!/usr/bin/env python3
"""Garmin GPX ingestion script (Linux, GVFS/MTP).

- Discovers Garmin MTP mount via `gio mount -li`
- Ensures the device is mounted (optionally mounts it)
- Copies GPX files into a clean raw layout:
    ~/GPS/_raw/<year>/<download_date>/<device_id>/<Category>/...

- Writes:
    - manifest.json
    - manifest.csv
    - checksums.sha256

Categories (current defaults):
- Current:   .../GARMIN/GPX/Current/*.gpx   (Current.gpx, Temp.gpx, etc.)
- Archive:   .../GARMIN/GPX/Archive/**/*.gpx
- Waypoints: .../GARMIN/GPX/Waypoints_*.gpx (in GPX root)
- Other:     any other *.gpx under .../GARMIN/GPX/

This script is intentionally "ingest only": it does not normalize or edit GPX content.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional, Tuple
import xml.etree.ElementTree as ET


class NoMtpDeviceError(RuntimeError):
    """Raised when no MTP device is mounted/visible via gio."""

# ----------------------------
# GPSmax Configuration
# ----------------------------
# When running this file directly, ensure the repo root is importable so
# that `from gpsmax.config import load_config` works.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from gpsmax.config import load_config
except Exception:
    load_config = None # type: ignore
    # Optionally: Keep this quiet unless you want visibility
    print(f"Warning: GPSmax config unavailable ({e}); using defaults.", file=sys.stderr)

# ----------------------------
# Logging
# ----------------------------

def log(msg: str) -> None:
    ts = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"{ts}  {msg}", file=sys.stderr)


# ----------------------------
# Utilities
# ----------------------------

def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def slugify_device_model(s: str) -> str:
    """Convert human model strings to a path-safe slug."""
    s = s.strip()
    s = re.sub(r"^Garmin[_\s]+", "", s, flags=re.IGNORECASE)
    s = s.replace("_", " ")
    s = re.sub(r"[^A-Za-z0-9 ]+", "", s)
    s = re.sub(r"\s+", "", s)
    return s.lower() or "garmin"


def parse_garmin_device_xml_description(xml_path: Path) -> Optional[str]:
    """Best-effort parse of GarminDevice.xml for a model description."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        desc = root.findtext(".//Description")
        if desc:
            return desc.strip()
    except Exception:
        return None
    return None


# ----------------------------
# GVFS/MTP discovery
# ----------------------------

@dataclass(frozen=True)
class MtpMountInfo:
    mtp_uri: str            # e.g. mtp://Garmin_GPSMAP_67_0000ced81822/
    host: str               # e.g. Garmin_GPSMAP_67_0000ced81822
    gvfs_mount: Path        # e.g. /run/user/1000/gvfs/mtp:host=Garmin_GPSMAP_67_0000ced81822


def discover_mtp_mount() -> MtpMountInfo:
    """Parse `gio mount -li` to find the first MTP default_location/activation_root."""
    cp = run(["gio", "mount", "-li"], check=True)
    text = cp.stdout

    m = re.search(r"^\s*activation_root=(mtp://[^/]+/)\s*$", text, flags=re.MULTILINE)
    if not m:
        m = re.search(r"^\s*default_location=(mtp://[^/]+/)\s*$", text, flags=re.MULTILINE)
    if not m:
        raise NoMtpDeviceError("No MTP device found. Connect and mount your Garmin, then try again.")
    
    mtp_uri = m.group(1)
    host = re.sub(r"^mtp://", "", mtp_uri).rstrip("/")

    uid = os.getuid()
    gvfs_mount = Path(f"/run/user/{uid}/gvfs/mtp:host={host}")
    return MtpMountInfo(mtp_uri=mtp_uri, host=host, gvfs_mount=gvfs_mount)


def ensure_mounted(mtp_uri: str) -> None:
    """Attempt to mount the MTP URI (idempotent in typical cases)."""
    log(f"Ensuring mount: {mtp_uri}")
    cp = run(["gio", "mount", mtp_uri], check=False)
    if cp.returncode != 0:
        log(f"gio mount returned {cp.returncode}: {cp.stderr.strip()}")


# ----------------------------
# Ingest mapping
# ----------------------------

@dataclass
class FileRecord:
    category: str
    source_path: str         # full source path in GVFS
    source_relpath: str      # relative to GVFS mount root
    dest_path: str           # full destination path
    dest_relpath: str        # relative to DEST_BASE
    bytes: int
    mtime_utc: str
    sha256: str


def classify_gpx(relpath_posix: str) -> Tuple[str, Optional[str]]:
    """Return (category, sub_relpath_under_category) or ('Skip', None)."""
    p = relpath_posix

    m = re.search(r"/GARMIN/GPX/Current/(.+\.gpx)$", p, flags=re.IGNORECASE)
    if m:
        return "Current", m.group(1)

    m = re.search(r"/GARMIN/GPX/Archive/(.+\.gpx)$", p, flags=re.IGNORECASE)
    if m:
        return "Archive", m.group(1)

    m = re.search(r"/GARMIN/GPX/(Waypoints_[^/]+\.gpx)$", p, flags=re.IGNORECASE)
    if m:
        return "Waypoints", m.group(1)

    m = re.search(r"/GARMIN/GPX/(.+\.gpx)$", p, flags=re.IGNORECASE)
    if m:
        return "Other", m.group(1)

    return "Skip", None


def iter_gpx_files(gvfs_root: Path) -> Iterable[Tuple[Path, str]]:
    """Yield (absolute_path, relpath_posix) for *.gpx under likely GARMIN trees."""
    for root, dirs, files in os.walk(gvfs_root):
        if "GARMIN" not in root.upper():
            dirs[:] = []
            continue
        for fn in files:
            if fn.lower().endswith(".gpx"):
                ap = Path(root) / fn
                rel = ap.relative_to(gvfs_root).as_posix()
                yield ap, rel


def derive_device_id(mtp: MtpMountInfo) -> str:
    """Derive a friendly, path-safe device_id."""
    host = mtp.host

    if host.startswith("Garmin_") and "_" in host:
        model_part = host
        if re.search(r"_[0-9a-fA-F]{6,}$", host):
            model_part = host.rsplit("_", 1)[0]
        model_part = model_part.replace("Garmin_", "", 1)
        model_slug = slugify_device_model(model_part)
        if model_slug:
            return model_slug

    candidates = [
        mtp.gvfs_mount / "Internal Storage" / "GARMIN" / "GarminDevice.xml",
        mtp.gvfs_mount / "GARMIN" / "GarminDevice.xml",
        mtp.gvfs_mount / "Internal Storage" / "Garmin" / "GarminDevice.xml",
    ]
    for c in candidates:
        if c.is_file():
            desc = parse_garmin_device_xml_description(c)
            if desc:
                return slugify_device_model(desc)

    h = hashlib.sha256(host.encode("utf-8")).hexdigest()[:8]
    return f"device_{h}"


# ----------------------------
# Main ingest
# ----------------------------

def main() -> int:
    # Define and parse out command line arguments.
    ap = argparse.ArgumentParser(description="Ingest Garmin GPX data over GVFS/MTP into a clean raw layout.")
    ap.add_argument("--raw-root", default=None,
                    help="Root directory for raw ingests (default: from GPSmax config or ~/GPS/_raw)")
    ap.add_argument("--download-date", default=None,
                    help="Override ingest download date (YYYY-MM-DD). Default: today (local).")
    ap.add_argument("--year", default=None,
                    help="Override year folder under raw root. Default: current year (local).")
    ap.add_argument("--device-id", default=None,
                    help="Override device_id folder name (otherwise auto-detected).")
    ap.add_argument("--mtp-uri", default=None,
                    help="Override MTP URI (e.g. mtp://Garmin_.../). Otherwise discovered via gio mount -li.")
    ap.add_argument("--no-mount", action="store_true",
                    help="Do not attempt to mount; assume already mounted.")
    ap.add_argument("--csv", action="store_true",
                    help="Write manifest.csv in addition to manifest.json.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Plan actions, but do not copy files or write outputs.")
    ap.add_argument("--verbose", action="store_true",
                    help="More logging.")
    args = ap.parse_args()

    # Resolve raw_root using precedence:
    # - CLI flag --raw-root (highest)
    # - environment variables / config (via gpsmax.config)
    # - fallback default ~/GPS/_raw
    if args.raw_root:
        raw_root = Path(args.raw_root).expanduser()
    else:
        if load_config is not None:
            cfg = load_config()
            raw_root = cfg.paths.raw_root
        else:
            raw_root = (Path.home() / "GPS" / "_raw").expanduser()

    now_local = dt.datetime.now().astimezone()
    download_date = args.download_date or now_local.date().isoformat()
    year = args.year or f"{now_local.year:04d}"

    # Establish the mtp-uri
    if args.mtp_uri:
        mtp_uri = args.mtp_uri
        host = re.sub(r"^mtp://", "", mtp_uri).rstrip("/")
        uid = os.getuid()
        mtp = MtpMountInfo(mtp_uri=mtp_uri, host=host, gvfs_mount=Path(f"/run/user/{uid}/gvfs/mtp:host={host}"))
    else:
        try:
            mtp = discover_mtp_mount()
        except NoMtpDeviceError as e:
            log(str(e))
            log("Tip: confirm it appears in Thunar, or run: gio mount -li")
            return 2

    log(f"Found MTP URI: {mtp.mtp_uri}")
    log(f"Using GVFS mount path: {mtp.gvfs_mount}")

    if not args.no_mount:
        ensure_mounted(mtp.mtp_uri)

    if not mtp.gvfs_mount.exists():
        log(f"ERROR: GVFS mount path does not exist: {mtp.gvfs_mount}")
        log("Try opening the device in your file manager once (GVFS), then re-run, or mount manually with `gio mount`.")
        return 2

    device_id = args.device_id or derive_device_id(mtp)
    dest_base = raw_root / year / download_date / device_id

    log(f"Destination base: {dest_base}")
    
    # Build a mapping detailing what files are to be copied, from where and to where.
    # If no .gpx files exist then continue.
    planned: list[tuple[str, Path, Path]] = []
    for src_abs, rel_posix in iter_gpx_files(mtp.gvfs_mount):
        cat, sub = classify_gpx(rel_posix)
        if cat == "Skip" or sub is None:
            continue
        dest_abs = dest_base / cat / Path(sub)
        planned.append((cat, src_abs, dest_abs))

    if not planned:
        log("No GPX files found to ingest.")
        return 0

    if args.dry_run:
        log(f"DRY RUN: would ingest {len(planned)} file(s) into {dest_base}")
        if args.verbose:
            for cat, s, d in planned[:50]:
                log(f"  {cat}: {s} -> {d}")
            if len(planned) > 50:
                log(f"  ... ({len(planned)-50} more)")
        return 0

    # Ensure that the destination directory exists, and create it if it does not.
    dest_base.mkdir(parents=True, exist_ok=True)

    records: list[FileRecord] = []  # Structured ingest metadata
    checksum_lines: list[str] = []  # sha256 checksums
    ingest_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    copied = 0
    # For each file in the planned listing
    for cat, src_abs, dest_abs in planned:
        # Check whether the filename already exists in the destination folder.
        dest_abs.parent.mkdir(parents=True, exist_ok=True)

        # Collision handling: if same content, skip; else suffix with src hash prefix.
        if dest_abs.exists():
            src_hash = sha256_file(src_abs)
            dest_hash = sha256_file(dest_abs)
            if src_hash == dest_hash:
                if args.verbose:
                    log(f"Skip identical existing file: {dest_abs}")
                continue
            dest_abs = dest_abs.with_name(f"{dest_abs.stem}__{src_hash[:8]}{dest_abs.suffix}")

        # Execute the file transfer and increment the copied counter.
        shutil.copy2(src_abs, dest_abs)
        copied += 1

        st = dest_abs.stat()  # Metadata for the current file
        digest = sha256_file(dest_abs) # SHA256 digest of current file

        # Relative paths for source and destination.
        src_rel = src_abs.relative_to(mtp.gvfs_mount).as_posix()
        dest_rel = dest_abs.relative_to(dest_base).as_posix()

        # Build manifest record.
        rec = FileRecord(
            category=cat,
            source_path=str(src_abs),
            source_relpath=src_rel,
            dest_path=str(dest_abs),
            dest_relpath=dest_rel,
            bytes=st.st_size,
            mtime_utc=dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).isoformat(timespec="seconds"),
            sha256=digest,
        )

        records.append(rec)   # Append record to the list of manifest records
        checksum_lines.append(f"{digest}  {dest_rel}")   # Append checksum digest to list of checksums

        # Live logging output if --verbose is specified in arguments.
        if args.verbose:
            log(f"Copied ({cat}): {src_abs} -> {dest_abs}")

    # Define the file paths for checksums and manifests.
    checksums_path = dest_base / "checksums.sha256"
    manifest_json_path = dest_base / "manifest.json"
    manifest_csv_path = dest_base / "manifest.csv"

    # Write checksum_lines to checkums.sha256.
    checksums_path.write_text("\n".join(checksum_lines) + ("\n" if checksum_lines else ""), encoding="utf-8")

    # Structure and populate manifest documentation.
    manifest_doc = {
        "ingest_utc": ingest_utc,
        "device": {
            "device_id": device_id,
            "mtp_uri": mtp.mtp_uri,
            "mtp_host": mtp.host,
            "gvfs_mount": str(mtp.gvfs_mount),
        },
        "destination": {
            "dest_base": str(dest_base),
            "layout": "<raw_root>/<year>/<download_date>/<device_id>/<Category>/...",
        },
        "counts": {
            "planned": len(planned),
            "copied": copied,
            "records": len(records),
        },
        "files": [asdict(r) for r in records],
    }

    # Write JSON manifest file.
    manifest_json_path.write_text(json.dumps(manifest_doc, indent=2), encoding="utf-8")

    # Write CSV manifest if --csv is specified in arguments.
    if args.csv:
        with manifest_csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "category", "source_path", "source_relpath", "dest_path", "dest_relpath",
                "bytes", "mtime_utc", "sha256"
            ])
            w.writeheader()
            for r in records:
                w.writerow(asdict(r))

    log(f"Ingest complete: copied {copied} file(s).")
    log(f"Wrote: {checksums_path}")
    log(f"Wrote: {manifest_json_path}")
    if args.csv:
        log(f"Wrote: {manifest_csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
