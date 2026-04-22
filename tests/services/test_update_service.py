"""Tests for ``src/services/update_service.py`` — pure-helper layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.update_service import decide_update


@dataclass
class FakeRelease:
    tag_name: str
    prerelease: bool = False
    assets: list[dict[str, Any]] = field(default_factory=list)


def _installer_asset(version: str, size: int = 1_000_000) -> dict[str, Any]:
    return {
        "name": f"WinScanLLM-Setup-{version}.exe",
        "browser_download_url": f"https://github.com/o/r/releases/download/v{version}/WinScanLLM-Setup-{version}.exe",
        "digest": "sha256:" + ("a" * 64),
        "size": size,
    }


# --- decide_update ----------------------------------------------------------


def test_newer_stable_tag_triggers_update():
    rel = FakeRelease(tag_name="v1.2.3", assets=[_installer_asset("1.2.3")])
    info = decide_update(current="1.0.0", release=rel, include_prereleases=False, skipped="")
    assert info is not None
    assert info.version == "1.2.3"
    assert info.asset_url.endswith("WinScanLLM-Setup-1.2.3.exe")
    assert info.asset_digest == "sha256:" + ("a" * 64)
    assert info.asset_size == 1_000_000


def test_same_tag_returns_none():
    rel = FakeRelease(tag_name="v1.0.0", assets=[_installer_asset("1.0.0")])
    assert decide_update("1.0.0", rel, False, "") is None


def test_older_tag_returns_none():
    rel = FakeRelease(tag_name="v0.9.0", assets=[_installer_asset("0.9.0")])
    assert decide_update("1.0.0", rel, False, "") is None


def test_prerelease_filtered_by_default():
    rel = FakeRelease(tag_name="v1.2.3rc1", prerelease=True)
    assert decide_update("1.0.0", rel, include_prereleases=False, skipped="") is None


def test_prerelease_allowed_when_opted_in():
    rel = FakeRelease(tag_name="v1.2.3rc1", prerelease=True, assets=[_installer_asset("1.2.3rc1")])
    info = decide_update("1.0.0", rel, include_prereleases=True, skipped="")
    assert info is not None
    assert info.version == "1.2.3rc1"


def test_skipped_tag_is_respected():
    rel = FakeRelease(tag_name="v1.2.3")
    assert decide_update("1.0.0", rel, False, skipped="v1.2.3") is None


def test_invalid_version_returns_none():
    rel = FakeRelease(tag_name="not-a-version")
    assert decide_update("1.0.0", rel, False, "") is None


def test_no_installer_asset_returns_info_with_empty_url():
    """If GitHub shows a release with no .exe asset yet, we still compare
    versions but UpdateInfo url/digest are empty. The UI should treat this
    as not-actionable."""
    rel = FakeRelease(tag_name="v1.2.3", assets=[{"name": "source.tar.gz"}])
    info = decide_update("1.0.0", rel, False, "")
    assert info is not None
    assert info.asset_url == ""
    assert info.asset_digest is None
