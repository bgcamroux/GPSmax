# gpsmax/scripts/util/logging.py
from __future__ import annotations

import datetime

def utc_now_iso() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def log(msg: str) -> None:
    """Print a timestamped log line (local time with timezone)."""
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"{ts}  {msg}")


