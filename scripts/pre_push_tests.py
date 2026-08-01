#!/usr/bin/env python
"""Pre-push test gate launcher — run ``run_tests.py`` under the project venv.

pre-commit invokes ``local`` hooks with ``language: system``, i.e. whatever
``python`` is first on ``PATH``. On developer machines that is often the base
interpreter, which does not have pytest installed — so the ``pytest-fast``
pre-push hook fails with ``ModuleNotFoundError: No module named 'pytest'`` even
though the project venv has pytest available.

This launcher (stdlib only, so the base interpreter can run it) locates the
project's virtualenv interpreter and re-runs ``run_tests.py`` with it. It falls
back to the current interpreter when no venv is found — e.g. on CI, where pytest
is installed in the active environment.

Arguments are forwarded verbatim to ``run_tests.py``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_python() -> str:
    """Return the interpreter that has the test dependencies installed."""
    # 1. An already-activated virtualenv (respects a non-default venv).
    active = os.environ.get("VIRTUAL_ENV")
    if active:
        for rel in ("Scripts/python.exe", "bin/python"):
            candidate = Path(active) / rel
            if candidate.exists():
                return str(candidate)
    # 2. The project-local ./venv (Windows layout first, then POSIX).
    for rel in ("venv/Scripts/python.exe", "venv/bin/python"):
        candidate = REPO_ROOT / rel
        if candidate.exists():
            return str(candidate)
    # 3. Fall back to the interpreter running this launcher (e.g. CI).
    return sys.executable


def main() -> int:
    python = _resolve_python()
    cmd = [python, str(REPO_ROOT / "run_tests.py"), *sys.argv[1:]]
    return subprocess.call(cmd, cwd=str(REPO_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
