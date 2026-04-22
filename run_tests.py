#!/usr/bin/env python
"""
Test runner that ensures src/ is in Python path before running pytest.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py tests/config # Run specific directory
    python run_tests.py -k provider  # Run tests matching pattern

Environment tolerance (for the pytest-fast pre-push hook):
    1. pyproject.toml's addopts requires pytest-cov. When invoked from an
       env without pytest-cov, we override addopts to empty so plain pytest
       can still parse its args — tests run without coverage.
    2. The pre-push hook runs under whatever Python is on PATH when git
       invokes it. That is usually system Python, which does not have the
       app's production deps (PyQt6, ollama, etc.) installed. When invoked
       from pre-commit (PRE_COMMIT=1) in such an env, we print a clear
       message and exit 0 — the gate is skipped but not silently. A
       developer running the script directly still gets the real failure.
"""

import importlib.util
import os
import sys
from pathlib import Path

src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402  -- path setup must precede this import

# Sentinel app dependencies. If any of these cannot be imported, the
# invoking Python is almost certainly not the developer's venv and the
# test suite cannot meaningfully run.
_SENTINEL_APP_DEPS: tuple[str, ...] = ("ollama", "PyQt6", "PIL")


def _coverage_available() -> bool:
    return importlib.util.find_spec("pytest_cov") is not None


def _app_deps_available() -> bool:
    return all(importlib.util.find_spec(dep) is not None for dep in _SENTINEL_APP_DEPS)


def _running_under_pre_commit() -> bool:
    return os.environ.get("PRE_COMMIT") == "1"


def _build_pytest_args(user_args: list[str], coverage_available: bool) -> list[str]:
    if coverage_available:
        return list(user_args)
    filtered = [a for a in user_args if not a.startswith("--cov") and a != "--no-cov"]
    return ["-o", "addopts=", *filtered]


def _should_skip_due_to_missing_env(app_deps_available: bool, under_pre_commit: bool) -> bool:
    return under_pre_commit and not app_deps_available


def main() -> int:
    if _should_skip_due_to_missing_env(_app_deps_available(), _running_under_pre_commit()):
        print(
            "[run_tests] Skipping pre-push test gate: application dependencies "
            "are not installed in the current Python environment.",
            file=sys.stderr,
        )
        print(
            "[run_tests] Activate your venv (`.\\venv\\Scripts\\Activate.ps1`) "
            "to enable the pytest-fast pre-push hook. Push allowed.",
            file=sys.stderr,
        )
        return 0

    raw_args = sys.argv[1:] if len(sys.argv) > 1 else ["tests/", "-v"]
    args = _build_pytest_args(raw_args, _coverage_available())
    return int(pytest.main(args))


if __name__ == "__main__":
    sys.exit(main())
