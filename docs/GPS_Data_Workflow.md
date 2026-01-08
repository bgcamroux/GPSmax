# GPS Data Organization & Workflow (Linux + Garmin GPSMAP 67)

This document defines a durable, low-friction workflow for managing GPS track data on a Linux desktop, with a focus on separation of concerns, auditability, and tool-agnostic storage.

## Goals

- Preserve an immutable “source of truth” for every download from the GPS device.
- Maintain a curated library that remains usable regardless of GIS software changes.
- Make processing repeatable: raw → normalized → curated → exported.
- Support downstream uses (mapping, geotagging, sharing, OSM contributions) cleanly.

## Directory Structure

Recommended top-level layout:

```text
~/GPS/
├── _raw/
│   └── garmin_gpsmap67/
│       └── YYYY/
│           └── YYYY-MM-DD/
├── tracks/
│   ├── hiking/
│   ├── cycling/
│   ├── roadtrip/
│   ├── geotagging/
│   └── misc/
├── waypoints/
├── routes/
├── maps/
├── exports/
│   ├── strava/
│   ├── osm/
│   ├── geojson/
│   └── kml/
└── index/
```

## Data Lifecycle Workflow

### 1) Capture
Record activities on the Garmin GPSMAP 67. Avoid editing on-device unless necessary.

### 2) Ingest (Device → Raw Snapshot)
Every download produces a dated snapshot under `_raw/.../YYYY/YYYY-MM-DD/`.

Artifacts:
- checksums.sha256
- manifest.json
- manifest.csv

### 3) Normalize
Normalize into new files; never modify raw.

### 4) Curate
Organize cleaned tracks into human-meaningful directories with canonical filenames.

### 5) Visualize / Edit
Use QMapShack as a viewer/editor, not a canonical database.

### 6) Index
Maintain a searchable index (SQLite, CSV, or Markdown).

### 7) Export
Generate disposable exports for sharing or publishing.

## Geotagging Pipeline

Use only cleaned, time-verified tracks from a dedicated geotagging folder.

## Version Control (Optional)
Git can be used to track changes to curated GPX files.

## Operational Checklist

1. Plug in device
2. Run ingest script
3. Verify manifest and checksums
4. Normalize selected tracks
5. Curate with canonical naming
