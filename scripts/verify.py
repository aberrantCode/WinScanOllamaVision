#!/usr/bin/env python
"""Local verification gate — reproduces the old GitHub Actions CI on the dev box.

We run verification locally instead of on GitHub Actions. This launcher is the
single source of truth for "is this change shippable?".

Two modes:

  --quick   ruff check + ruff format --check + mypy + the curated fast test
            subset (-n auto, no coverage). ~30-60 s. This is what the pre-push
            hook runs, so every push is gated without a multi-minute wait.

  (default) The full gate: everything in --quick, plus bandit, the complete
            pytest suite (no coverage gate — see below), and a package
            build + twine check. Run this before opening a PR or cutting a
            release: ``python scripts/verify.py`` (or ``scripts/verify.ps1``).

Coverage: the repo's ``--cov-fail-under=90`` gate only holds across the *full*
suite, which is not yet green end-to-end. The full mode here runs tests with
``--no-cov`` so the gate reports real pass/fail instead of a coverage floor.
Restoring the 90% coverage gate is tracked in the backlog.

Stdlib-only (so the base interpreter can run it); it resolves the project venv
the same way ``scripts/pre_push_tests.py`` does and runs every tool under that
interpreter.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The curated subset that is known-green and fast. Mirrors the pre-push
# scope: the UI/GUI/integration suites are excluded because the full suite
# is not yet green (see module docstring).
FAST_TEST_PATHS = [
    "tests/services",
    "tests/db",
    "tests/config",
    "tests/llm_providers",
]


def _resolve_python() -> str:
    """Return the interpreter that has the dev dependencies installed."""
    active = os.environ.get("VIRTUAL_ENV")
    if active:
        for rel in ("Scripts/python.exe", "bin/python"):
            candidate = Path(active) / rel
            if candidate.exists():
                return str(candidate)
    for rel in ("venv/Scripts/python.exe", "venv/bin/python"):
        candidate = REPO_ROOT / rel
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _run(name: str, argv: list[str]) -> tuple[str, bool]:
    """Run one gate step, streaming its output; return (name, passed)."""
    print(f"\n{'=' * 70}\n>> {name}\n{'=' * 70}", flush=True)
    code = subprocess.call(argv, cwd=str(REPO_ROOT))
    passed = code == 0
    print(f"-- {name}: {'PASS' if passed else f'FAIL (exit {code})'}", flush=True)
    return name, passed


def _steps(py: str, quick: bool) -> list[tuple[str, list[str]]]:
    """Build the ordered list of (name, argv) gate steps for the mode."""
    steps: list[tuple[str, list[str]]] = [
        ("ruff check", [py, "-m", "ruff", "check", "src/", "tests/"]),
        ("ruff format --check", [py, "-m", "ruff", "format", "--check", "src/", "tests/"]),
        (
            "mypy",
            [py, "-m", "mypy", "src/", "--ignore-missing-imports", "--no-strict-optional"],
        ),
    ]
    if quick:
        steps.append(
            (
                "pytest (fast subset)",
                [py, "-m", "pytest", *FAST_TEST_PATHS, "--no-cov", "-n", "auto", "-q"],
            )
        )
        return steps

    # Full mode: security scan, whole suite (no coverage gate), package build.
    steps.append(("bandit", [py, "-m", "bandit", "-r", "src/", "-c", "pyproject.toml", "-q"]))
    steps.append(("pytest (full suite)", [py, "-m", "pytest", "tests/", "--no-cov", "-q"]))
    steps.append(("python -m build", [py, "-m", "build"]))
    steps.append(("twine check", [py, "-m", "twine", "check", "dist/*"]))
    return steps


def main() -> int:
    quick = "--quick" in sys.argv[1:]
    py = _resolve_python()
    mode = "quick" if quick else "full"
    print(f"Local verification gate ({mode} mode) — interpreter: {py}")

    results = [_run(name, argv) for name, argv in _steps(py, quick)]

    print(f"\n{'=' * 70}\nSUMMARY ({mode})\n{'=' * 70}")
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    failed = [name for name, passed in results if not passed]
    if failed:
        print(f"\n{len(failed)} step(s) failed: {', '.join(failed)}")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
