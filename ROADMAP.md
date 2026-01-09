# GPSmax — Project Summary & Roadmap

## Project Intent (The Big Picture)

**GPSmax** is a personal, Unix-style GPS data pipeline designed to:

- Preserve *all* data produced by GPS receivers (tracks, sensors, metadata)
- Enforce clear separation between **raw data**, **working data**, and **derived products**
- Make every transformation **auditable, reproducible, and reversible**
- Support long-term analysis, visualization, and geotagging workflows
- Avoid vendor lock-in and GUI fragility while remaining tool-agnostic

The system favors **small, composable tools** over monoliths, and treats GPX files as first-class, inspectable artifacts rather than opaque blobs.

---

## Phase 0 — The Spark (Shell Script Era)

### Problem Identified
- Manual GPX management from a Garmin GPSMAP 67 was fragile and inconsistent
- MTP access under Linux was awkward but solvable
- QMapShack was powerful but heavy for simple ingestion and organization

### Initial Solution
A shell script using:
- `gio mount` for MTP access
- `cp` for copying GPX files
- Directory mirroring of the Garmin internal structure

### Lessons Learned
- Shell scripting hits complexity limits quickly (parsing, manifests, checksums)
- Device paths are unwieldy and should not define long-term storage layout
- Provenance and auditability matter more than initially expected

---

## Phase 1 — Python Ingestion + Provenance (Complete)

### Deliverables
- `garmin_ingest.py`: robust ingestion with device auto-detection
- `_raw` data store with stable directory layout
- Manifest generation with SHA-256 checksums
- Graceful handling of absent hardware
- Centralized configuration system
- SQLite Phase A schema and manifest importer
- Clean Git separation between code and runtime data

---

## Phase 2 — Normalization (In Progress)

### Goals
- Produce canonical, readable GPX files from `_raw`
- Preserve original sensor data
- Attach human intent via sidecar metadata

### Features
- fzf-driven interactive selection
- Meaningful track naming
- Activity labeling (hiking, cycling, driving, skiing, etc.)
- Geotag candidate flags
- Normalized output into `_work`

---

## Phase 3 — Visualization + Pruning (Planned)

### 3.1 — Quick View / Diagnostics
Tool: `gps_plot.py`

- Lightweight XY geometry plotting
- Optional stop highlighting
- Optional overlays (normalized vs pruned)
- PNG/SVG export for diagnostics
- Read-only, no data mutation

### 3.2 — Pruning
Tool: `gps_prune.py`

- Non-destructive pruning of normalized tracks
- Collapse stationary jitter (rests, fuel stops, photo pauses)
- Remove obvious GPS spikes
- Derived output: `track.pruned.gpx`
- Full provenance tracking (parameters, hashes, metrics)

---

## Phase 3+ — Track Thumbnails (Recommended)

### Strategy
Generate thumbnails as derived artifacts on disk and index them in SQLite.

Filesystem (per track):
```
track.gpx
track.pruned.gpx
track.sidecar.json
thumb.pruned.png
thumb.pruned.svg (optional)
```

SQLite:
- Table: `track_previews`
- Stores relative path, hash, size, format, variant, and generation parameters

Rationale:
- Keeps SQLite lean
- Artifacts are rebuildable
- Enables fast visual browsing

---

## Phase 4 — Export & Publishing (Future)

### 4.1 — Export Tool
Tool: `gps_export.py`

- GPX, GeoJSON, KML/KMZ exports
- Reduced-resolution tracks
- Activity-specific layers
- QGIS/QMapShack-friendly bundles

### 4.2 — Photobook & Trip Map Production

Primary downstream use case:
- Create high-quality maps for photobooks and trip reports

Workflow support:
1. Activity layers (hike/bike/drive/ski)
2. Photo location layers (EXIF-derived or time-correlated)
3. QGIS/QMapShack-ready project bundles
4. SVG/PDF outputs suitable for print

GPSmax prepares structured inputs; final cartography remains in GIS tools.

---

## Near-Term Priority Order

1. Complete normalization workflow
2. Implement quick-view plotting tool
3. Implement pruning with provenance
4. Add thumbnail generation + indexing
5. Implement export + photobook map bundles

---

## Architectural Principles

- Raw data is immutable
- Derived data is reproducible
- Filesystem stores artifacts; SQLite stores truth
- Visualization precedes transformation
- Future-proofing is intentional, not accidental
