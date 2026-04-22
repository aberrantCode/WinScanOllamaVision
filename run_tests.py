#!/usr/bin/env python
"""
Test runner that ensures src/ is in Python path before running pytest.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py tests/config # Run specific directory
    python run_tests.py -k provider  # Run tests matching pattern

Coverage tolerance:
    pyproject.toml's [tool.pytest.ini_options] addopts enables pytest-cov.
    When this script is invoked from an environment that lacks pytest-cov
    (notably the pre-push hook running under system Python instead of the
    developer's venv), plain pytest cannot parse --cov flags and crashes
    with "unrecognized arguments: --cov=src ...". To keep the runner
    usable in both environments, we detect whether pytest-cov is importable
    and, if not, override addopts to empty and filter --cov* flags out of
    the user-supplied arguments. Tests still run — just without coverage.
"""

import importlib.util
import sys
from pathlib import Path

src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402  -- path setup must precede this import


def _coverage_available() -> bool:
    return importlib.util.find_spec("pytest_cov") is not None


def _build_pytest_args(user_args: list[str], coverage_available: bool) -> list[str]:
    if coverage_available:
        return list(user_args)
    filtered = [a for a in user_args if not a.startswith("--cov") and a != "--no-cov"]
    return ["-o", "addopts=", *filtered]


def main() -> int:
    raw_args = sys.argv[1:] if len(sys.argv) > 1 else ["tests/", "-v"]
    args = _build_pytest_args(raw_args, _coverage_available())
    return int(pytest.main(args))


if __name__ == "__main__":
    sys.exit(main())
