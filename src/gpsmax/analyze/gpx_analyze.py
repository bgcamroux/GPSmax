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


# ---------------------------
# GPSmax Configuration
# ---------------------------
try:
    from gpsmax.config import load_config
except Exception as e:
    load_config = None


# ---------------------------
# fzf selection
# ---------------------------
# This section needs to be moved to a module



