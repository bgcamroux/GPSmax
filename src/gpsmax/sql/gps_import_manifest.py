#!/usr/bin/env python3
"""gps_import_manifest.py

Import a garmin_ingest.py manifest.json into SQLite (Phase A: ingestion only).

Usage:
  ./gps_import_manifest.py --db ~/GPS/_db/gps.sqlite --schema gps_schema.sql \
      ~/GPS/_raw/2026/2026-01-06/gpsmap67/manifest.json

Idempotency:
- Re-importing the same manifest will not duplicate file rows for that run because of a
  UNIQUE index on (ingest_run_id, dest_relpath).
- A run is identified by (ingest_utc, device_id, dest_base). If it already exists, it is reused.

"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# ----------------------------
# GPSmax configuration
# ----------------------------
# When running this file directly (python scripts/sql/gps_import_manifest.py),
# add the repo root to sys.path so `from gpsmax.config import load_config` works.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from gpsmax.config import load_config
except Exception:
    load_config = None # type: ignore

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def ensure_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    conn.executescript(schema_path.read_text(encoding="utf-8"))

def get_or_create_run(conn: sqlite3.Connection, manifest: dict[str, Any], manifest_path: Path) -> int:
    ingest_utc = manifest.get("ingest_utc")
    device = manifest.get("device", {})
    destination = manifest.get("destination", {})
    counts = manifest.get("counts", {})

    device_id = device.get("device_id") or "unknown"
    dest_base = destination.get("dest_base") or ""

    if not ingest_utc or not dest_base:
        raise ValueError("manifest.json missing required fields: ingest_utc and/or destination.dest_base")

    row = conn.execute(
        """SELECT ingest_run_id
             FROM ingest_runs
             WHERE ingest_utc = ? AND device_id = ? AND dest_base = ?""",
        (ingest_utc, device_id, dest_base),
    ).fetchone()

    if row:
        ingest_run_id = int(row[0])
        conn.execute(
            """UPDATE ingest_runs
                 SET mtp_uri = ?,
                     mtp_host = ?,
                     gvfs_mount = ?,
                     layout = ?,
                     planned_count = ?,
                     copied_count = ?,
                     record_count = ?,
                     manifest_json_path = COALESCE(manifest_json_path, ?)
                 WHERE ingest_run_id = ?""",
            (
                device.get("mtp_uri"),
                device.get("mtp_host"),
                device.get("gvfs_mount"),
                destination.get("layout"),
                counts.get("planned"),
                counts.get("copied"),
                counts.get("records"),
                str(manifest_path),
                ingest_run_id,
            ),
        )
        return ingest_run_id

    cur = conn.execute(
        """INSERT INTO ingest_runs (
               ingest_utc, device_id, mtp_uri, mtp_host, gvfs_mount,
               dest_base, layout, planned_count, copied_count, record_count,
               manifest_json_path, imported_utc
             ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            ingest_utc,
            device_id,
            device.get("mtp_uri"),
            device.get("mtp_host"),
            device.get("gvfs_mount"),
            dest_base,
            destination.get("layout"),
            counts.get("planned"),
            counts.get("copied"),
            counts.get("records"),
            str(manifest_path),
            utc_now_iso(),
        ),
    )
    return int(cur.lastrowid)

def import_files(conn: sqlite3.Connection, ingest_run_id: int, manifest: dict[str, Any]) -> tuple[int, int]:
    inserted = 0
    skipped = 0

    for f in manifest.get("files", []):
        cur = conn.execute(
            """INSERT OR IGNORE INTO ingest_files (
                   ingest_run_id, category, source_path, source_relpath,
                   dest_path, dest_relpath, bytes, mtime_utc, sha256
                 ) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                ingest_run_id,
                f.get("category"),
                f.get("source_path"),
                f.get("source_relpath"),
                f.get("dest_path"),
                f.get("dest_relpath"),
                int(f.get("bytes", 0)),
                f.get("mtime_utc"),
                f.get("sha256"),
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    return inserted, skipped

def main() -> int:
    ap = argparse.ArgumentParser(description="Import garmin_ingest manifest.json into SQLite.")
    ap.add_argument("manifest_json", help="Path to manifest.json")
    ap.add_argument("--db", default=None,
                    help="SQLite DB path (default: ~/GPS/_db/gps.sqlite)")
    ap.add_argument("--schema", default=str(Path(__file__).with_name("gps_schema.sql")),
                    help="Schema SQL path (default: gps_schema.sql next to this script)")
    args = ap.parse_args()

    manifest_path = Path(args.manifest_json).expanduser().resolve()
    schema_path = Path(args.schema).expanduser().resolve()
    if args.db:
        db_path = Path(args.db).expanduser().resolve()
    else:
        if load_config is not None:
            cfg = load_config()
            db_path = cfg.paths.sqlite_path.expanduser().resolve()
        else:
            db_path = (Path.home() / "GPS" / "_db" / "gps.sqlite").expanduser().resolve()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    conn = connect(db_path)
    try:
        ensure_schema(conn, schema_path)
        run_id = get_or_create_run(conn, manifest, manifest_path)
        inserted, skipped = import_files(conn, run_id, manifest)
        conn.commit()
    finally:
        conn.close()

    print(f"Imported run_id={run_id} into {db_path}")
    print(f"Files inserted={inserted}, skipped(existing)={skipped}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
