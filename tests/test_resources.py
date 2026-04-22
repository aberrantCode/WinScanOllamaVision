"""Tests for src/resources.py asset-path resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from resources import _candidate_bases, asset_path


def test_dev_mode_returns_real_asset_path():
    """In dev (not frozen), assets/icon.png should resolve to the repo asset."""
    path = asset_path("icon.png")
    assert os.path.exists(path), f"Expected asset at {path}"


def test_dev_mode_candidate_is_repo_root():
    bases = _candidate_bases()
    assert len(bases) == 1
    repo_root = Path(__file__).resolve().parent.parent
    assert Path(bases[0]).resolve() == repo_root


def test_frozen_mode_uses_meipass_first(tmp_path, monkeypatch):
    """In frozen mode with _MEIPASS set, that directory should be tried first."""
    fake_meipass = tmp_path / "meipass"
    fake_meipass.mkdir()
    (fake_meipass / "assets").mkdir()
    (fake_meipass / "assets" / "scanner.gif").write_bytes(b"gif-bytes")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)

    path = asset_path("scanner.gif")
    assert Path(path) == fake_meipass / "assets" / "scanner.gif"


def test_frozen_mode_falls_back_to_internal_subdir(tmp_path, monkeypatch):
    """PyInstaller 6+ onedir puts data under ``_internal/`` next to the exe."""
    fake_exe = tmp_path / "app.exe"
    fake_exe.write_bytes(b"")
    (tmp_path / "_internal" / "assets").mkdir(parents=True)
    (tmp_path / "_internal" / "assets" / "scanner.gif").write_bytes(b"gif")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    path = asset_path("scanner.gif")
    assert Path(path) == tmp_path / "_internal" / "assets" / "scanner.gif"


def test_missing_asset_returns_best_guess_without_crashing():
    """If nothing matches, return the first candidate path anyway."""
    path = asset_path("does-not-exist.foo")
    assert path.endswith(os.path.join("assets", "does-not-exist.foo"))


def test_asset_path_supports_subpaths():
    path = asset_path("images", "scan_error.png")
    assert os.path.exists(path), f"Expected asset at {path}"
