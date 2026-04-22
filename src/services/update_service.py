"""GitHub Releases–driven self-update for WinScanLLM.

This module is split into pure helpers (testable without Qt) and the
``UpdateService`` Qt facade (``_qt.py``). Pure helpers live here so that
the test suite can exercise them on machines without PyQt6 installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import requests
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


# ---------------------------------------------------------------------------
# Cache short-circuit (Task 4)
# ---------------------------------------------------------------------------


CACHE_TTL = timedelta(hours=6)


def should_check_now(last_checked_at: datetime | None) -> bool:
    if last_checked_at is None:
        return True
    return datetime.now(timezone.utc) - last_checked_at >= CACHE_TTL


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Host allowlist (Task 5)
# ---------------------------------------------------------------------------


_ALLOWED_DOWNLOAD_HOSTS: frozenset[str] = frozenset(
    {
        "github.com",
        "api.github.com",
        "objects.githubusercontent.com",
    }
)


def is_allowed_download_url(url: str) -> bool:
    """Accept only HTTPS URLs whose host is a GitHub Releases host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.hostname in _ALLOWED_DOWNLOAD_HOSTS


# ---------------------------------------------------------------------------
# Download + SHA-256 verification (Task 6)
# ---------------------------------------------------------------------------


class DownloadError(Exception):
    """Raised when the installer download fails to verify or the URL is unsafe."""


_DEFAULT_UA = "WinScanLLM-updater"


def download_and_verify(
    url: str,
    expected_digest: str,
    dest_dir: Path,
    user_agent: str = _DEFAULT_UA,
    timeout: tuple[float, float] = (5.0, 30.0),
) -> Path:
    """Download the file at ``url`` to ``dest_dir``, verify SHA-256 matches
    ``expected_digest`` (format ``"sha256:<hex>"``), and return the path.

    Fails closed: any host-allowlist violation, network error, or hash
    mismatch deletes the partial file and raises ``DownloadError``.
    """
    if not is_allowed_download_url(url):
        raise DownloadError(f"download host not allowed: {url}")
    if not expected_digest.startswith("sha256:"):
        raise DownloadError(f"unsupported digest format: {expected_digest}")
    expected_hex = expected_digest.split(":", 1)[1].lower()

    dest_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".exe", dir=str(dest_dir))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        hasher = hashlib.sha256()
        with requests.get(
            url,
            headers={"User-Agent": user_agent},
            stream=True,
            timeout=timeout,
            allow_redirects=True,
        ) as response:
            response.raise_for_status()
            if not is_allowed_download_url(response.url):
                raise DownloadError(f"redirect host not allowed: {response.url}")
            with tmp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1 << 16):
                    if chunk:
                        hasher.update(chunk)
                        handle.write(chunk)
        if hasher.hexdigest().lower() != expected_hex:
            raise DownloadError("downloaded file hash mismatch")
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return tmp_path


# ---------------------------------------------------------------------------
# GitHub Releases API fetch (Task 7)
# ---------------------------------------------------------------------------


def _github_api_url(owner: str, repo: str) -> str:
    return f"https://api.github.com/repos/{owner}/{repo}/releases/latest"


def fetch_latest_release(
    owner: str,
    repo: str,
    user_agent: str = _DEFAULT_UA,
    timeout: float = 10.0,
) -> FetchedRelease | None:
    """Fetch the latest release metadata. Returns ``None`` on any non-fatal
    error (network, 404, malformed JSON) — upstream logs + retries later.
    """
    try:
        response = requests.get(
            _github_api_url(owner, repo),
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": user_agent,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None
    return FetchedRelease(
        tag_name=str(data.get("tag_name", "")),
        prerelease=bool(data.get("prerelease", False)),
        assets=list(data.get("assets") or []),
    )
