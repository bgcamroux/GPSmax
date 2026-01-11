# gpsmax/scripts/util/subprocess.py
from __future__ import annotations

import subprocess
from typing import Sequence

def run_cmd(cmd: Sequence[str],
        *, check: bool = True, capture_output: bool = True,
        text: bool = True,) -> subprocess.CompletedProcess:
    """
    Run a command and return CompletedProcess.

    Defaults:
      - capture_output=True to make error reporting easier
      - text=True for string stdout/stderr
      - check=True to raise CalledProcessError on non-zero exit
    """
    return subprocess.run(
        list(cmd),
        check=check,
        capture_output=capture_output,
        text=text,
    )
