#!/usr/bin/env python3
"""

"""

from __future__ import annotations

import argparse
import sys
import datetime as dt
from pathlib import Path
from dataclasses import dataclass

from gpsmax.analyze.track import analyze_track
#from gpsmax.formats.gpx import TrackPoint, extract_trackpoints, read_gpx
from gpsmax.util.fzf import fzf_select_paths


# ---------------------------
# GPSmax Configuration
# ---------------------------
try:
    from gpsmax.config import load_config
except Exception as e:
    load_config = None


def print_report(path: Path, stats: dict, *, tsv: bool) -> None:
    if tsv:
        print(
            f"{path}\t"
            f"{stats.get('points', 0)}\t"
            f"{stats.get('segments', 0)}\t"
            f"{stats.get('distance_m', 0.0):.2f}\t"
            f"{stats.get('duration_s', 0.0):.1f}\t"
            f"{stats.get('avg_speed_mps', 0.0):.3f}\t"
            f"{stats.get('max_speed_mps', 0.0):.3f}"
        )
    else:
        print(f"\n{path}")
        print(f"  points        : {stats.get('points', 0)}")
        print(f"  segments      : {stats.get('segments', 0)}")
        print(f"  distance (m)  : {stats.get('distance_m', 0.0):.2f}")
        print(f"  duration (s)  : {stats.get('duration_s', 0.0):.1f}")
        print(f"  avg speed m/s : {stats.get('avg_speed_mps', 0.0):.3f}")
        print(f"  max speed m/s : {stats.get('max_speed_mps', 0.0):.3f}")


    
def main() -> int:
    ap = argparse.ArgumentParser(description="GPSmax: Analyze GPX file(s).")
    ap.add_argument("gpx", nargs="*",
                    help="One or more GPXfiles (from _work). If omitted, use fzf selection.")
    ap.add_argument("--work-root", default=None,
                    help="Working root (default: from GPSmax config or ~/GPS/_work")
    ap.add_argument("--tsv", action="store_true",
                    help="Print tab-separated output (good for piping).")
    
    args = ap.parse_args()  # parse out the arguments into `args`
    cfg = load_config() if load_config is not None else None  # load configuration file if present

    selected: list[Path] = []    # selected list of input tracks
    
    if args.work_root:
        work_root = Path(args.work_root).expanduser()
    else:
        work_root = cfg.paths.work_root if cfg else (Path.home() / "GPS" / "_work")

    
    work_root = work_root.expanduser()
    gpx_files = sorted(work_root.rglob("*.gpx")) 
    if not gpx_files:
        raise SystemExit(f"No GPX files found under {work_root}")

    # Keep selection UI identical to normalize: search by filename, output real path.
    selected = fzf_select_paths(
        gpx_files,
        header="Select GPX file(s) to analyze:",
        multi=True,
        preview=None,   # add preview later if wanted
    )

    if args.tsv:
        print("file\tpoints\tsegments\tdistance_m\tduration_s\tavg_speed_mps\tmax_speed_mps")

    for path in selected:
        if not path.is_file():
            print(f"Skipping (not a file): {path}")
            continue
        stats = analyze_track(path)
        print_report(path, stats, tsv=args.tsv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
