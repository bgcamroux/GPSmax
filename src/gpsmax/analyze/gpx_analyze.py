#!/usr/bin/env python3
"""

"""

from __future__ import annotations

import argparse
import sys
import datetime as dt
from pathlib import Path
from dataclasses import dataclass

from gpsmax.analyze.track import compute_step_metrics, analyze_track
from gpsmax.normalize.gpx import TrackPoint, extract_trackpoints, read_gpx
from gpsmax.util.fzf import fzf_select_paths


# ---------------------------
# GPSmax Configuration
# ---------------------------
try:
    from gpsmax.config import load_config
except Exception as e:
    load_config = None


work_root = cfg.paths.work_root
gpx_files = sorted(work_root.rglob("*.gpx")) 

if not gpx_files:
    raise SystemExit("No GPX files found under _work")

selected = fzf_select_paths(
    gpx_files,
    header="Select GPX file(s) to analyze:",
    multi=True,
    preview_cmd=[],   # reuse or simplify preview
)

analyze_track(path) for path in selected
