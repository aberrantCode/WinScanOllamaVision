"""Tests that [Updates] section defaults are seeded on a fresh config."""

from __future__ import annotations

from pathlib import Path

from config.config_manager import ConfigManager


def _fresh_config(tmp_path: Path) -> ConfigManager:
    return ConfigManager(config_file=str(tmp_path / "settings.ini"))


def test_updates_section_exists_on_fresh_config(tmp_path: Path):
    cm = _fresh_config(tmp_path)
    assert "Updates" in cm.config


def test_check_on_startup_defaults_to_true(tmp_path: Path):
    cm = _fresh_config(tmp_path)
    assert cm.get_bool("Updates", "check_on_startup", default=False) is True


def test_include_prereleases_defaults_to_false(tmp_path: Path):
    cm = _fresh_config(tmp_path)
    assert cm.get_bool("Updates", "include_prereleases", default=True) is False


def test_skipped_version_defaults_empty(tmp_path: Path):
    cm = _fresh_config(tmp_path)
    assert cm.get_setting("Updates", "skipped_version") == ""


def test_last_check_and_known_version_default_empty(tmp_path: Path):
    cm = _fresh_config(tmp_path)
    assert cm.get_setting("Updates", "last_check_iso") == ""
    assert cm.get_setting("Updates", "last_known_version") == ""
