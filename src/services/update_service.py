"""GitHub Releases–driven self-update for WinScanLLM.

This module is split into pure helpers (testable without Qt) and the
``UpdateService`` Qt facade (``_qt.py``). Pure helpers live here so that
the test suite can exercise them on machines without PyQt6 installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from packaging.version import InvalidVersion, Version

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UpdateInfo:
    """What the app needs to know to decide + perform an update."""

    version: str
    asset_url: str
    asset_digest: str | None  # "sha256:<hex>" as returned by GitHub Releases v2
    asset_size: int


@dataclass(frozen=True)
class FetchedRelease:
    """Minimal subset of a GitHub release JSON that the update logic needs."""

    tag_name: str
    prerelease: bool
    assets: list[dict[str, Any]]


class _ReleaseLike(Protocol):
    tag_name: str
    prerelease: bool
    assets: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Version comparison (Task 3)
# ---------------------------------------------------------------------------


def _strip_v(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def _find_installer_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for asset in assets:
        name = asset.get("name", "")
        if name.startswith("WinScanLLM-Setup-") and name.endswith(".exe"):
            return asset
    return None


def decide_update(
    current: str,
    release: _ReleaseLike,
    include_prereleases: bool,
    skipped: str,
) -> UpdateInfo | None:
    """Return an ``UpdateInfo`` if ``release`` is a newer non-skipped stable
    (or opted-in pre-release) version than ``current``; else ``None``.
    """
    if release.tag_name == skipped:
        return None
    if release.prerelease and not include_prereleases:
        return None
    try:
        current_version = Version(current)
        new_version = Version(_strip_v(release.tag_name))
    except InvalidVersion:
        return None
    if new_version <= current_version:
        return None
    asset = _find_installer_asset(release.assets or [])
    return UpdateInfo(
        version=_strip_v(release.tag_name),
        asset_url=asset.get("browser_download_url", "") if asset else "",
        asset_digest=asset.get("digest") if asset else None,
        asset_size=int(asset.get("size", 0)) if asset else 0,
    )
