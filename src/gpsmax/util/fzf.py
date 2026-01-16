# gpsmax/util/fzf.py
"""
Helper functions for path selection using `fzf`
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from shutil import which

from gpsmax.errors import FzfNotFoundError


def fzf_select_paths(
        paths: list[Path], *,
        header: str,
        multi: bool = True,
        preview: str | None = None,
) -> list[Path]:
    
    if not which("fzf"):
        raise FzfNotFoundError("fzf not found on PATH")

    lines = [f"{p.name}\t{p}" for p in paths]
    input_text = "\n".join(lines) + "\n"
    selected: list[Path] = []

    cmd = [
        "fzf",
        "--ansi",
        "--delimiter=\t",
        "--nth=1",
        "--with-nth=1",
        "--height=60%",
        "--layout=reverse",
        "--border",
        "--header", header,
    ]

    if multi:
        cmd.append("--multi")

    if preview:
        cmd.extend(["--preview", preview])
        cmd.extend(["--preview-window", "right:60%:wrap"])

    proc = subprocess.run(
        cmd,
        input=input_text.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if proc.returncode not in (0, 130):
        raise GPSmaxError(proc.stderr.decode(errors="replace"))

    out = proc.stdout.decode().strip()
    if not out:
        return []
    
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # line is: "name<TAB>fullpath"
        path_str = line.split("\t", 1)[1] if "\t" in line else line
        selected.append(Path(path_str).expanduser().resolve())
    return selected
#    return [Path(line.split("\t", 1)[1]) for line in out.splitlines()]
