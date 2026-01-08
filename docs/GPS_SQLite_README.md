# GPS SQLite (Phase A: Ingestion)

This phase stores ingestion history (what files were copied, when, from where, to where, with what hashes).

## Files
- `gps_schema.sql` — SQLite schema (tables, indexes, view)
- `gps_import_manifest.py` — importer for `manifest.json`

## Recommended database location
- `~/GPS/_db/gps.sqlite`

## Import an ingest manifest
Example (adjust date/device_id as needed):

```bash
mkdir -p ~/GPS/_db
python3 gps_import_manifest.py --db ~/GPS/_db/gps.sqlite --schema gps_schema.sql \
  ~/GPS/_raw/2026/2026-01-06/gpsmap67/manifest.json
```

## Quick verification queries

```bash
sqlite3 ~/GPS/_db/gps.sqlite
```

```sql
SELECT ingest_run_id, ingest_utc, device_id, copied_count
FROM ingest_runs
ORDER BY ingest_utc DESC;

SELECT category, COUNT(*) AS n
FROM ingest_files
GROUP BY category
ORDER BY n DESC;

SELECT sha256, COUNT(*) AS n
FROM ingest_files
GROUP BY sha256
HAVING n > 1
ORDER BY n DESC;
```

## Next phase (after normalization stabilizes)
We will extend the schema to store:
- normalized artifacts
- sidecar metadata
- presets / parameters
- segments (e.g., driving vs walking)
- geotagging workflow state

All linked back to `ingest_files`.
