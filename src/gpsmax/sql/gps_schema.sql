-- gps_schema.sql
PRAGMA foreign_keys = ON;

-- Phase A: ingestion-only schema.

CREATE TABLE IF NOT EXISTS ingest_runs (
    ingest_run_id      INTEGER PRIMARY KEY,
    ingest_utc         TEXT NOT NULL,
    device_id          TEXT NOT NULL,
    mtp_uri            TEXT,
    mtp_host           TEXT,
    gvfs_mount         TEXT,
    dest_base          TEXT NOT NULL,
    layout             TEXT,
    planned_count      INTEGER,
    copied_count       INTEGER,
    record_count       INTEGER,
    manifest_json_path TEXT,
    imported_utc       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ingest_runs_time_device
ON ingest_runs (ingest_utc, device_id);

CREATE TABLE IF NOT EXISTS ingest_files (
    ingest_file_id  INTEGER PRIMARY KEY,
    ingest_run_id   INTEGER NOT NULL REFERENCES ingest_runs(ingest_run_id) ON DELETE CASCADE,
    category        TEXT NOT NULL,
    source_path     TEXT NOT NULL,
    source_relpath  TEXT NOT NULL,
    dest_path       TEXT NOT NULL,
    dest_relpath    TEXT NOT NULL,
    bytes           INTEGER NOT NULL,
    mtime_utc       TEXT NOT NULL,
    sha256          TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ingest_files_run_destrel
ON ingest_files (ingest_run_id, dest_relpath);

CREATE INDEX IF NOT EXISTS idx_ingest_files_sha256 ON ingest_files (sha256);
CREATE INDEX IF NOT EXISTS idx_ingest_files_category ON ingest_files (category);
CREATE INDEX IF NOT EXISTS idx_ingest_files_run ON ingest_files (ingest_run_id);

CREATE VIEW IF NOT EXISTS v_ingest_runs_latest AS
SELECT r.*
FROM ingest_runs r
JOIN (
  SELECT device_id, MAX(ingest_utc) AS max_ingest_utc
  FROM ingest_runs
  GROUP BY device_id
) t
ON r.device_id = t.device_id AND r.ingest_utc = t.max_ingest_utc;
