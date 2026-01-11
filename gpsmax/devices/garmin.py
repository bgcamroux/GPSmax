# gpsmax/devices/garmin.py
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from gpsmax.devices.mtp import MtpMountInfo
from gpsmax.util.paths import slugify

def slugify_device_model(model: str) -> str:
    """
    Convert a Garmin model string into a friendly, path-safe slug.
    Falls back to 'garmin' if slugify returns empty.
    """
    s = s.strip()
    s = re.sub(r"^Garmin[_\s]+", "", s, flags=re.IGNORECASE)
    s = s.replace("_", " ")
    s = re.sub(r"[^A-Za-z0-9 ]+", "", s)
    s = re.sub(r"\s+", "", s)
    return s.lower() or "garmin"


def parse_garmin_device_xml_description(xml_path: Path) -> Optional[str]:
    """
    Best-effort parse of GarminDevice.xml to extract a device description/model.
    This varies across devices, so we search several likely elements.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except (ET.ParseError, OSError) as e:
        log(f"Could not parse Garmin device XML ({xml_path}): {e}")
        log(f"Will attempt generic device identification instead.")
        return None

    # Try common tags.
    candidates = [
        ".//Description",
        ".//Model/Description",
        ".//Model/Name",
        ".//Model",
        ".//Device/Model",
    ]

    for xp in candidates:
        text = root.findtext(xp)
        if text and text.strip():
            return text.strip()
        
    # Fallback to a more generic scan
    for el in root.iter():
        if el.tag.lower().endswith("description"):
            if el.text and el.text.strip():
                return el.text.strip()
    return None


def derive_device_id(mtp: MtpMountInfo) -> str:
    """Derive a friendly, path-safe device_id."""
    host = mtp.host

    # Prefer parsing host if it looks like: Garmin_GPSMAP_67_<suffix>
    if host.startswith("Garmin_") and "_" in host:
        model_part = host
        if re.search(r"_[0-9a-fA-F]{6,}$", host):
            model_part = host.rsplit("_", 1)[0]
        model_part = model_part.replace("Garmin_", "", 1)
        model_slug = slugify_device_model(model_part)
        if model_slug:
            return model_slug

    # Try GarminDevice.xml in a few typical locations
    candidates = [
        mtp.gvfs_mount / "Internal Storage" / "GARMIN" / "GarminDevice.xml",
        mtp.gvfs_mount / "GARMIN" / "GarminDevice.xml",
        mtp.gvfs_mount / "Internal Storage" / "Garmin" / "GarminDevice.xml",
    ]
    for c in candidates:
        if c.is_file():
            desc = parse_garmin_device_xml_description(c)
            if desc:
                return slugify_device_model(desc)

    # Fallback: stable-ish hash of host
    h = hashlib.sha256(host.encode("utf-8")).hexdigest()[:8]
    return f"garmin_{h}"
