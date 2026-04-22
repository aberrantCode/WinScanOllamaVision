"""Resource-path resolution that works in both dev and PyInstaller-frozen apps.

In a normal source checkout the project root is ``<repo>/``, with ``src/`` and
``assets/`` as siblings. In a PyInstaller onedir bundle the runtime layout
differs: ``sys.frozen`` is set, and data files are unpacked into a path
exposed via ``sys._MEIPASS`` (onefile) or located next to / under ``_internal``
next to the executable (onedir, PyInstaller 6+). Callers should never compute
asset paths by walking up from ``__file__`` — that only works in dev mode.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _candidate_bases() -> list[Path]:
    """Return ordered candidate directories that may contain the ``assets/`` tree."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        bases: list[Path] = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bases.append(Path(meipass))
        bases.extend([exe_dir, exe_dir / "_internal"])
        return bases

    # Dev mode: this file lives at src/resources.py → repo root is one level up.
    return [Path(__file__).resolve().parent.parent]


def asset_path(*parts: str) -> str:
    """Return the absolute path to an asset under ``assets/<*parts>``.

    Tries each candidate base directory in order and returns the first hit.
    If nothing matches, returns the best-guess path so the caller can report
    a meaningful file-not-found message (instead of a synthesized one that
    hides the real lookup).
    """
    for base in _candidate_bases():
        candidate = base.joinpath("assets", *parts)
        if candidate.exists():
            return str(candidate)
    return str(_candidate_bases()[0].joinpath("assets", *parts))
