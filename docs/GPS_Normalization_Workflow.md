# GPS Track Normalization Process

This document describes the **normalization phase** of the GPS data workflow. Normalization converts raw, device-generated GPX files into clean, predictable, analysis-ready GPX files without modifying the original raw data.

---

## 1. What Normalization Is

Normalization is the process of transforming raw GPX files into a consistent, curated-ready form.

Key principle:

**Normalization produces new files. Raw data is never edited.**

Think of it as:
- RAW → TIFF (photography)
- Logs → normalized tables (databases)

---

## 2. Why Normalization Is Necessary

Garmin devices (including the GPSMAP 67) commonly produce GPX files with:

- Multiple track segments per activity
- Auto-archived fragments
- Device-specific extensions
- Redundant or noisy metadata
- GPS jitter when stopped
- Separate “Current”, “Archive”, and “Auto” tracks

Normalization ensures that:
- Each file represents one logical activity
- Metadata is predictable
- Downstream tools behave consistently
- Geotagging and analytics are reliable

---

## 3. Inputs and Outputs

### Input (read-only)

```text
~/GPS/_raw/garmin_gpsmap67/YYYY/YYYY-MM-DD/_device/...
```

Examples:
- Current.gpx
- Archive/*.gpx
- Archive/Auto/*.gpx

### Output (new files)

```text
~/GPS/_work/
```

or directly into curated locations:

```text
~/GPS/tracks/<activity>/<year>/
```

---

## 4. Core Normalization Operations

Not every track needs every step. Apply only what makes sense.

---

### 4.1 Merge Track Segments

Garmin often splits a single outing into multiple segments or files.

Goal:
- One track = one activity

Example (single file):
```bash
gpsbabel -i gpx -f input.gpx -x track,merge -o gpx -F merged.gpx
```

Example (multiple files):
```bash
gpsbabel -i gpx -f part1.gpx -f part2.gpx -x track,merge -o gpx -F merged.gpx
```

---

### 4.2 Normalize Timestamps

Ensure all timestamps are explicit and consistent (usually UTC).

Goals:
- No floating local time
- Predictable geotagging behavior

Python concept:
```python
point.time = point.time.astimezone(timezone.utc)
```

---

### 4.3 Clean Metadata

Garmin GPX files often contain:
- Firmware identifiers
- Device-specific extensions

Remove anything you do not actively use, while retaining:
- Coordinates
- Elevation
- Time
- Optional sensor data (HR, cadence)

---

### 4.4 Clean Jitter and Stops (Situational)

Common issues:
- GPS drift when stopped
- Parking-lot spiderwebs

Example:
```bash
gpsbabel -i gpx -f input.gpx -x track,speed=0.3 -o gpx -F cleaned.gpx
```

Use conservatively, especially for hiking.

---

### 4.5 Split Tracks (If Needed)

Use when:
- A recording spans multiple days
- Drive + walk are in one file
- Recording was left running

Split by:
- Time gaps
- Distance gaps
- Manual editing (QMapShack)

---

## 5. Metadata Enrichment

Normalization is the right time to add semantic meaning.

Recommended fields:
- Name
- Description
- Keywords

Example:
```xml
<name>2025-08-25 Kananaskis Hike</name>
<keywords>hike,kananaskis,alberta</keywords>
```

---

## 6. Output Handling

After normalization:
1. Inspect visually
2. Rename canonically:
   ```text
   YYYY-MM-DD_location_activity.gpx
   ```
3. Move into curated library
4. Optionally commit to version control
5. Update index

---

## 7. What Normalization Is Not

Normalization is not:
- Archival storage
- Export formatting
- Tool-specific database import
- Publishing

Those occur later in the workflow.

---

## 8. Normalization Checklist

Before calling a file “curated”:

- One logical activity?
- Correct timestamps?
- Clean segments?
- Meaningful metadata?
- Confident geotagging?

If yes, it is normalized.
