"""Tests for ``src/services/update_service.py`` — pure-helper layer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from services.update_service import (
    CACHE_TTL,
    DownloadError,
    FetchedRelease,
    decide_update,
    download_and_verify,
    fetch_latest_release,
    is_allowed_download_url,
    load_cache,
    save_cache,
    should_check_now,
)


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


# --- should_check_now / cache (Task 4) --------------------------------------


def test_cache_fresh_suppresses_check():
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    assert should_check_now(recent) is False


def test_cache_expired_allows_check():
    old = datetime.now(timezone.utc) - CACHE_TTL - timedelta(seconds=1)
    assert should_check_now(old) is True


def test_no_cache_allows_check():
    assert should_check_now(None) is True


def test_load_cache_missing_file_returns_empty(tmp_path: Path):
    assert load_cache(tmp_path / "missing.json") == {}


def test_load_cache_malformed_returns_empty(tmp_path: Path):
    path = tmp_path / "cache.json"
    path.write_text("{not-json", encoding="utf-8")
    assert load_cache(path) == {}


def test_save_then_load_cache_roundtrips(tmp_path: Path):
    path = tmp_path / "nested" / "cache.json"
    save_cache(path, {"last_known_version": "1.2.3"})
    assert json.loads(path.read_text()) == {"last_known_version": "1.2.3"}
    assert load_cache(path) == {"last_known_version": "1.2.3"}


# --- is_allowed_download_url (Task 5) ---------------------------------------


@pytest.mark.parametrize(
    "url, allowed",
    [
        ("https://github.com/o/r/releases/download/v1/file.exe", True),
        ("https://api.github.com/repos/o/r/releases/assets/123", True),
        ("https://objects.githubusercontent.com/x/y/z.exe", True),
        ("https://evil.com/payload.exe", False),
        ("http://github.com/o/r/releases/download/v1/file.exe", False),  # HTTP
        ("ftp://github.com/o/r", False),
        ("", False),
        ("not-a-url", False),
    ],
)
def test_download_host_allowlist(url: str, allowed: bool):
    assert is_allowed_download_url(url) is allowed


# --- download_and_verify (Task 6) -------------------------------------------


def _fake_stream_response(body: bytes, final_url: str | None = None) -> MagicMock:
    response = MagicMock()
    response.__enter__ = MagicMock(return_value=response)
    response.__exit__ = MagicMock(return_value=False)
    response.iter_content = lambda chunk_size: [body]
    response.headers = {"content-length": str(len(body))}
    response.url = final_url or "https://objects.githubusercontent.com/payload.exe"
    response.raise_for_status = MagicMock()
    return response


def test_download_stores_file_when_hash_matches(tmp_path: Path):
    body = b"installer bytes"
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    with patch(
        "services.update_service.requests.get",
        return_value=_fake_stream_response(body),
    ):
        out = download_and_verify(
            url="https://github.com/o/r/releases/download/v1/WinScanLLM-Setup-1.0.0.exe",
            expected_digest=digest,
            dest_dir=tmp_path,
        )
    assert out.exists()
    assert out.read_bytes() == body


def test_download_rejects_hash_mismatch_and_cleans_up(tmp_path: Path):
    body = b"tampered"
    wrong = "sha256:" + hashlib.sha256(b"different").hexdigest()
    with (
        patch(
            "services.update_service.requests.get",
            return_value=_fake_stream_response(body),
        ),
        pytest.raises(DownloadError, match="hash"),
    ):
        download_and_verify(
            url="https://github.com/o/r/releases/download/v1/WinScanLLM-Setup-1.0.0.exe",
            expected_digest=wrong,
            dest_dir=tmp_path,
        )
    # no leftover files in dest_dir
    assert list(tmp_path.iterdir()) == []


def test_download_refuses_disallowed_initial_host(tmp_path: Path):
    with pytest.raises(DownloadError, match="host"):
        download_and_verify(
            url="https://evil.com/payload.exe",
            expected_digest="sha256:" + "0" * 64,
            dest_dir=tmp_path,
        )


def test_download_refuses_disallowed_redirect_host(tmp_path: Path):
    body = b"bytes"
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    response = _fake_stream_response(body, final_url="https://evil.com/payload.exe")
    with (
        patch("services.update_service.requests.get", return_value=response),
        pytest.raises(DownloadError, match="redirect"),
    ):
        download_and_verify(
            url="https://github.com/o/r/releases/download/v1/WinScanLLM-Setup-1.0.0.exe",
            expected_digest=digest,
            dest_dir=tmp_path,
        )


def test_download_rejects_unsupported_digest_format(tmp_path: Path):
    with pytest.raises(DownloadError, match="digest"):
        download_and_verify(
            url="https://github.com/o/r/releases/download/v1/WinScanLLM-Setup-1.0.0.exe",
            expected_digest="md5:abcd",
            dest_dir=tmp_path,
        )


# --- fetch_latest_release (Task 7) ------------------------------------------


def test_fetch_latest_release_parses_github_response():
    payload = {
        "tag_name": "v1.2.3",
        "prerelease": False,
        "assets": [{"name": "WinScanLLM-Setup-1.2.3.exe"}],
    }
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)
    with patch("services.update_service.requests.get", return_value=response):
        result = fetch_latest_release("owner", "repo")
    assert isinstance(result, FetchedRelease)
    assert result.tag_name == "v1.2.3"
    assert result.prerelease is False
    assert result.assets == [{"name": "WinScanLLM-Setup-1.2.3.exe"}]


def test_fetch_latest_release_returns_none_on_http_error():
    import requests as _requests

    response = MagicMock()
    response.raise_for_status = MagicMock(side_effect=_requests.HTTPError("500"))
    with patch("services.update_service.requests.get", return_value=response):
        assert fetch_latest_release("owner", "repo") is None


def test_fetch_latest_release_returns_none_on_network_error():
    import requests as _requests

    with patch(
        "services.update_service.requests.get",
        side_effect=_requests.ConnectionError("offline"),
    ):
        assert fetch_latest_release("owner", "repo") is None


def test_fetch_latest_release_returns_none_on_malformed_json():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(side_effect=ValueError("bad json"))
    with patch("services.update_service.requests.get", return_value=response):
        assert fetch_latest_release("owner", "repo") is None
