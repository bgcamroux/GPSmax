# gpsmax/formats/gpx.py
"""
GPX helpers for GPSmax

This module is intentionally format-focused:
- GPX namespace handling
- safely reading and writing ElementTree
- extracting useful metadata (times, etc)
- "normalization" at the XML-structure level (not pruning/segmentation)

Key design principle:
  Keep orchestration (paths, sidecars, manifests, user interaction) in scripts,
  separate from GPX parsing and transformation logic (here).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

# GPX 1.1 default namespace
GPX_NS = {"gpx": "http://www.topografix.com/GPX/1/1"}

def qn(tag: str) -> str:
    """
    Build an ElementTree-qualified name for a GPX tag.

    ElementTree represents namespaced tags internally as
      "{namespace-uri}tag"
    """
    return f"{{{GPX_NS['gpx']}}}{tag}"


def _parse_gpx_time(text: str) -> Optional[_dt.datetime]:
    """
    Parse an ISO-8601 timestamp commonly found in GPX <time> nodes.

    Expected examples:
      - "2026-01-02T21:14:44Z"
      - "2026-01-02T21:14:44.123Z"
      - "2026-01-02T21:14:44+00:00"
    """
    if not text:
        return None
    s = text.strip()
    if not s:
        return None

    # ElementTree GPX times commonly use Z for UTC.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    try:
        dt = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None

    # Ensure tz-aware; if naive, assume UTC (conservative for GPX sources)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)

    return dt.astimezone(_dt.timezone.utc)


def _format_gpx_time(dt: _dt.datetime) -> str:
    """
    Format a tz-aware datetime as GPX time (UTC with Z).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    dt_utc = dt.astimezone(_dt.timezone.utc)
    # Use seconds resolution for readability and stability.
    return dt_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _indent(elem: ET.Element, level: int = 0, indent: str = "  ") -> None:
    """
    In-place pretty-printer for ElementTree output. Eliminates double blank-line
    issues by explicitly controlling .text/.tail.
    """
    i = "\n" + level * indent
    j = "\n" + (level -1) * indent if level > 0 else "\n"

    children = list(elem)
    if children:
        if elem.text is None or not elem.text.strip():
            elem.text = i + indent
        for child in children:
            _indent(child, level + 1, indent=indent)
        if children[-1].tail is None or not children[-1].tail.strip():
            children[-1].tail = i
    if elem.tail is None or not elem.tail.strip():
        elem.tail = j


def read_gpx(path: Path) -> ET.ElementTree:
    """
    Read a GPX file into an ElementTree.

    Raises:
      ET.ParseError, OSError
    """
    return ET.parse(path)


def write_gpx(root: ET.Element, out_path: Path, *, pretty: bool = True) -> None:
    """
    Write a GPX XML tree to disk.

    - pretty=True applies indentation for human readability
    - writes UTF-8 with XML declaration
    """
    if pretty:
        _indent(root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)


def first_time_utc_from_gpx(root: ET.Element) -> Optional[_dt.datetime]:
    """
    Return the earliest trackpoint time (UTC) in a GPX document, if any.

    Preference order:
      - first <trkpt><time> found in document order
      - metadata time as a fallback (less reliable)
    """
    # Trackpoints
    for t in root.findall(".//gpx:trkpt/gpx:time", GPX_NS):
        dt = _parse_gpx_time(t.text or "")
        if dt:
            return dt

    # Fallback: metadata time
    mt = root.find(".//gpx:metadata/gpx:time", GPX_NS)
    if mt is not None:
        dt = _parse_gpx_time(mt.text or "")
        if dt:
            return dt

    return None


def _ensure_child(parent: ET.Element, tag: str) -> ET.Element:
    """
    Ensure a single child element exists and return it.
    """
    child = parent.find(qn(tag))
    if child is None:
        child = ET.SubElement(parent, qn(tag))
    return child


def _find_first_trk(root: ET.Element) -> Optional[ET.Element]:
    return root.find("gpx:trk", GPX_NS)


def _find_or_create_metadata(root: ET.Element) -> ET.Element:
    md = root.find("gpx:metadata", GPX_NS)
    if md is None:
        # Insert metadata near the top for readability (after root attrs).
        md = ET.Element(qn("metadata"))
        # Insert as first child if possible.
        if len(root):
            root.insert(0, md)
        else:
            root.append(md)
    return md


@dataclass(frozen=True)
class TrackPoint:
    lat: float
    lon: float
    time: datetime
    ele: float | None = None


@dataclass(frozen=True)
class NormalizeResult:
    """
    Summary of XML-level normalization actions (useful for manifests/sidecars).
    """
    metadata_name_set: bool
    trk_name_set: bool
    metadata_time_set: bool
    trk_count: int
    first_time_utc: Optional[str]  # ISO string (UTC, Z) or None


def extract_trackpoints(tree: ET.ElementTree) -> list[TrackPoint]:
    """Extract ordered trackpoints from a GPX tree."""
    root = tree.getroot()
    pts: list[TrackPoint] = []

    for trkpt in root.findall(".//gpx:trkpt", GPX_NS):
        lat = float(trkpt.get("lat"))
        lon = float(trkpt.get("lon"))
        
        t = trkpt.findtext("gpx:time", namespaces=GPX_NS).strip()
        if not t:
            continue   # skip points without timestamps
        time = parse_time_utc(t)

        ele_text = trkpt.findtext("gpx:ele", namespaces=GPX_NS).strip()
        ele = float(ele_text) if ele_text else None

        pts.append(TrackPoint(lat=lat, lon=lon, time=time, ele=ele))

    return pts

    
def normalize_gpx(
        in_path: Path, out_path: Path, *,
        track_name: Optional[str] = None,
        set_metadata_name: bool = True,
        set_trk_name: bool = True,
        ensure_metadata_time: bool = True,
        pretty: bool = True,
) -> NormalizeResult:
    """
    Normalize a GPX file and write the result.

    Normalization performed (XML-level only):
      - Optionally set <metadata><name> to track_name
      - Optionally set <trk><name> to track_name
      - Optionally ensure <metadata><time> exists (UTC), using first trackpoint time
      - Pretty-print output (controlled indentation, no double-blank lines)

    Notes:
      - GPX remains WGS84 lat/lon; no projection work is done here.
      - No pruning/segmentation is done here; that belongs in later phases.

    Returns:
      NormalizeResult describing what happened.
    """
    tree = read_gpx(in_path)
    root = tree.getroot()

    # Count tracks (for sanity and future multi-track handling)
    trks = root.findall("gpx:trk", GPX_NS)
    trk_count = len(trks)

    md = _find_or_create_metadata(root)
    first_time = first_time_utc_from_gpx(root)

    metadata_name_set = False
    trk_name_set_flag = False
    metadata_time_set = False

    if track_name:
        if set_metadata_name:
            md_name = md.find("gpx:name", GPX_NS)
            if md_name is None:
                md_name = ET.SubElement(md, qn("name"))
            if (md_name.text or "").strip() != track_name:
                md_name.text = track_name
                metadata_name_set = True

        if set_trk_name:
            trk = _find_first_trk(root)
            if trk is not None:
                trk_name = trk.find("gpx:name", GPX_NS)
                if trk_name is None:
                    trk_name = ET.SubElement(trk, qn("name"))
                if (trk_name.text or "").strip() != track_name:
                    trk_name.text = track_name
                    trk_name_set_flag = True

    if ensure_metadata_time:
        md_time = md.find("gpx:time",GPX_NS)
        if md_time is None and first_time is not None:
            md_time = ET.SubElement(md, qn("time"))
            md_time.text = _format_gpx_time(first_time)
            metadata_time_set = True
        elif md_time is not None and md_time.text:
            # Normalize time formatting if parseable
            dt = _parse_gpx_time(md_time.text)
            if dt is not None:
                norm = _format_gpx_time(dt)
                if md_time.text != norm:
                    md_time.text = norm
                    metadata_time_set = True


    # Write out
    write_gpx(root, out_path, pretty=pretty)

    first_time_str = None
    if first_time is not None:
        first_time_str = _format_gpx_time(first_time)

    return NormalizeResult(
        metadata_name_set = metadata_name_set,
        trk_name_set = trk_name_set_flag,
        metadata_time_set = metadata_time_set,
        trk_count = trk_count,
        first_time_utc = first_time_str,
    )
