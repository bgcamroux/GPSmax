# GPSmax Phase B — Normalization

Normalization converts *device-centric* GPX files in `~/GPS/_raw/...` into *workflow-centric* artifacts in `~/GPS/_work/...`.

## Outputs

```
~/GPS/_work/<YYYY>/<YYYY-MM-DD>/<device_id>/<track_slug>/
  <track_slug>.gpx
  <track_slug>.sidecar.json

~/GPS/_work/manifests/
  normalize_<run_id>.json
```

## Geotagging intent

Sidecars include:

- `geotag.candidate` — indicates photos were taken and may be geotagged later
- `geotag.photos_pending` — workflow state flag

This avoids duplicating tracks across multiple category folders.

## Usage

### fzf selection (recommended)
```bash
python scripts/normalize/gps_normalize.py --prompt
```

### Explicit file(s)
```bash
python scripts/normalize/gps_normalize.py   ~/GPS/_raw/2026/2026-01-06/gpsmap67/Archive/2026-01-02\ 14.14.44.gpx   --prompt
```

### Non-interactive
```bash
python scripts/normalize/gps_normalize.py <file.gpx>   --title "2026-01-02_kananaskis_hike"   --activity hiking   --geotag
```
