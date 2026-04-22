"""Tests for the repo-root `run_tests.py` test runner.

Focused on the argument-building logic that makes the runner tolerant of
environments without `pytest-cov` installed (e.g. the pre-push hook running
under system Python instead of the developer's venv). Without this, every
push fails because pyproject.toml's addopts reference --cov flags that
plain pytest cannot parse.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_run_tests_module():
    """Load run_tests.py from the repo root as a module for direct testing."""
    repo_root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("repo_run_tests", repo_root / "run_tests.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_args_preserved_when_coverage_available():
    rt = _load_run_tests_module()
    assert rt._build_pytest_args(["tests/services", "-x"], coverage_available=True) == [
        "tests/services",
        "-x",
    ]


def test_addopts_stripped_when_coverage_missing():
    """Override addopts to empty so pyproject's --cov flags do not reach pytest."""
    rt = _load_run_tests_module()
    result = rt._build_pytest_args(["tests/services", "-x"], coverage_available=False)
    assert result[:2] == ["-o", "addopts="], result
    assert "tests/services" in result
    assert "-x" in result


def test_cov_flags_filtered_from_user_args_when_missing():
    """If the caller passed --cov* explicitly, drop those too; pytest would reject them."""
    rt = _load_run_tests_module()
    result = rt._build_pytest_args(
        ["tests/", "--cov=src", "--no-cov", "--cov-report=term-missing", "-x"],
        coverage_available=False,
    )
    assert "--cov=src" not in result
    assert "--no-cov" not in result
    assert "--cov-report=term-missing" not in result
    assert "tests/" in result
    assert "-x" in result


def test_coverage_available_detects_pytest_cov_truthfully():
    """The detector should return the actual import state of the running interpreter."""
    rt = _load_run_tests_module()
    expected = importlib.util.find_spec("pytest_cov") is not None
    assert rt._coverage_available() is expected


def test_skip_when_pre_commit_and_app_deps_missing():
    rt = _load_run_tests_module()
    assert rt._should_skip_due_to_missing_env(app_deps_available=False, under_pre_commit=True)


def test_do_not_skip_when_app_deps_present_even_under_pre_commit():
    rt = _load_run_tests_module()
    assert not rt._should_skip_due_to_missing_env(app_deps_available=True, under_pre_commit=True)


def test_do_not_skip_when_app_deps_missing_but_run_manually():
    """Developer running `python run_tests.py` directly must still see real failures."""
    rt = _load_run_tests_module()
    assert not rt._should_skip_due_to_missing_env(app_deps_available=False, under_pre_commit=False)


def test_running_under_pre_commit_reads_env_var(monkeypatch):
    rt = _load_run_tests_module()
    monkeypatch.setenv("PRE_COMMIT", "1")
    assert rt._running_under_pre_commit() is True
    monkeypatch.delenv("PRE_COMMIT", raising=False)
    assert rt._running_under_pre_commit() is False


def test_pre_push_hook_arg_shape_works_without_coverage():
    """Exact arg shape the .pre-commit-config.yaml pre-push hook passes."""
    rt = _load_run_tests_module()
    hook_args = [
        "tests/services",
        "tests/db",
        "tests/config",
        "tests/llm_providers",
        "--no-cov",
        "-x",
    ]
    result = rt._build_pytest_args(hook_args, coverage_available=False)
    assert result[:2] == ["-o", "addopts="]
    assert "--no-cov" not in result  # filtered because pytest-cov absent
    assert "-x" in result
    for path in ("tests/services", "tests/db", "tests/config", "tests/llm_providers"):
        assert path in result
