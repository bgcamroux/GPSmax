# gpsmax/devices/mtp.py
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from gpsmax.util.subprocess import run_cmd

@dataclass(frozen=True)
class MtpMountInfo:
    mtp_uri: str
    host: str
    gvfs_mount: Path

class NoMtpDeviceError(RuntimeError):
    """Raised when no MTP device mount is detected via GVFS/gio."""
    
_MTP_URI_RE = re.compile(
    r"(?m)^(?:\s*activation_root|\s*default_location)=(mtp://[^\s]+/)\s*$"
)

def discover_mtp_mount() -> MtpMountInfo:
    """
    Discover the first mounted MTP device from `gio mount -li`.

    Returns:
      MtpMountInfo(mtp_uri, host, gvfs_mount)

    Raises:
      RuntimeError if no MTP mount is found.
    """
    cp = run_cmd(["gio", "mount", "-li"])
    text = cp.stdout or ""
    m = _MTP_URI_RE.search(text)
    if not m:
        raise NoMtpDeviceError("Could not find an MTP mount in `gio mount -li` output.")

    mtp_uri = m.group(1)
    host = re.sub(r"^mtp://", "", mtp_uri).rstrip("/")
    uid = os.getuid()
    gvfs_mount = Path(f"/run/user/{uid}/gvfs/mtp:host={host}")
    return MtpMountInfo(mtp_uri=mtp_uri, host=host, gvfs_mount=gvfs_mount)
