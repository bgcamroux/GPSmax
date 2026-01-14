# gpsmax/analyze/track.py
"""
Track analysis functions for GPSmax
"""

from pathlib import Path
from haversine import haversine, Unit

from gpsmax.formats.gpx import read_gpx, extract_trackpoints


def compute_step_metrics(points):
    """Return per-segment dt (s), distance (m), speed (m/s)."""
    dts = []
    ds = []
    vs = []

    for p0, p1 in zip(points, points[1:]):
        dt_s = (p1.time - p0.time).total_seconds()
        if dt_s <= 0:
            continue

        d_m = haversine((p0.lat, p0.lon), (p1.lat, p1.lon), unit=Unit.METERS)
        v = d_m / dt_s

        dts.append(dt_s)
        ds.append(d_m)
        vs.append(v)

    return dts, ds, vs


def analyze_track(gpx_path: Path):
    tree = read_gpx(gpx_path)
    root = tree.getroot()
    points = extract_trackpoints(root)

    if len(points) < 2:
        return {"points": len(points), "segments": 0}

    dts, ds, vs = compute_step_metrics(points)

    return {
        "points": len(points),
        "segments": len(vs),
        "distance_m": sum(ds),
        "duration_s": sum(dts),
        "avg_speed_mps": (sum(ds) / sum(dts)) if sum(dts) else 0.0,
        "max_speed_mps": max(vs) if vs else 0.0,
    }
