# Windows Installer & Self-Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship WinScanLLM as a Windows installer that deploys to Program Files, auto-updates from GitHub Releases, uninstalls cleanly, and creates a working desktop icon.

**Architecture:** PyInstaller (onedir) produces `WinScanLLM/` folder; Inno Setup 6 wraps it as `WinScanLLM-Setup-<version>.exe`; on startup a background `UpdateService` polls GitHub Releases v2 API, compares versions with `packaging.version`, and on user confirmation downloads + SHA-256-verifies the new installer and hands off to Inno Setup with `/SILENT` (UAC required). User data in `%APPDATA%\WinScanLLM\` is untouched by install/upgrade/uninstall by default.

**Tech Stack:** Python 3.12, PyQt6, PyInstaller, Inno Setup 6, GitHub Actions (`windows-latest`), pytest, `requests`, `packaging`.

**Design reference:** `docs/plans/2026-04-22-windows-installer-design.md`

**Branch strategy:** Implementation lands on `feat/windows-installer` branched off `origin/dev`. Single PR back to `dev`.

---

## Task 0: Prerequisite — unblock pushes by fixing `run_tests.py` passthrough

**Why first:** Every subsequent task commits and pushes; the `pytest-fast` pre-push hook invokes `run_tests.py` with pytest coverage flags it doesn't currently accept. Without this fix, every push needs `--no-verify`.

**Files:**
- Modify: `scripts/run_tests.py` (actual path — verify with `Glob: scripts/run_tests.py`)
- Also check: `run_tests.py` at repo root (if it's the one invoked by the hook — inspect `.pre-commit-config.yaml` first)

**Step 1: Identify which `run_tests.py` the hook invokes**

Run: Read `.pre-commit-config.yaml` and find the `pytest-fast` hook's `entry` line.
Expected: some variation of `python run_tests.py ...` or `python scripts/run_tests.py ...`.

**Step 2: Read the current `run_tests.py` to understand its argparse usage**

Look for `argparse.ArgumentParser()`. The bug is almost certainly `parse_args()` being called (which errors on unknown args) instead of `parse_known_args()`.

**Step 3: Write a failing test**

Create: `tests/test_run_tests_passthrough.py`

```python
import subprocess
import sys
from pathlib import Path

def test_run_tests_forwards_unknown_pytest_args_to_pytest():
    """Hook passes --no-cov; run_tests.py must forward it without error."""
    repo_root = Path(__file__).resolve().parent.parent
    # Use --collect-only so we don't actually execute tests
    result = subprocess.run(
        [sys.executable, "run_tests.py", "tests/", "--collect-only", "-q", "--no-cov"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert "unrecognized arguments" not in result.stderr, result.stderr
    assert result.returncode in (0, 5)  # 5 = no tests collected; ok for smoke
```

**Step 4: Run the test — it should fail**

Run: `python -m pytest tests/test_run_tests_passthrough.py -v`
Expected: FAIL with "unrecognized arguments: --no-cov" in stderr.

**Step 5: Fix `run_tests.py`**

Change `args = parser.parse_args()` → `args, extra = parser.parse_known_args()` and forward `extra` to the pytest invocation (append to `pytest_args` list before `pytest.main(pytest_args)`).

**Step 6: Run the test — it should pass**

Run: `python -m pytest tests/test_run_tests_passthrough.py -v`
Expected: PASS.

**Step 7: Commit and push (WITHOUT --no-verify)**

```bash
git checkout -b fix/run-tests-passthrough origin/dev
git add run_tests.py tests/test_run_tests_passthrough.py
git commit -m "fix: Forward unknown pytest args in run_tests.py"
git push -u origin fix/run-tests-passthrough
```

Open a PR to `dev` and merge it before starting Task 1. All subsequent pushes on `feat/windows-installer` will use the fixed hook.

---

## Task 1: Create `feat/windows-installer` branch and version file

**Files:**
- Create: `src/__version__.py`
- Modify: `src/main.py` (import and log version at startup)

**Step 1: Create the branch**

```bash
git fetch origin
git checkout -b feat/windows-installer origin/dev
```

**Step 2: Write the failing test**

Create: `tests/test_version.py`

```python
import re
from src import __version__ as version_module

def test_version_string_is_pep440_compatible():
    from packaging.version import Version
    Version(version_module.__version__)  # raises if invalid

def test_version_matches_x_y_z_pattern_for_stable():
    v = version_module.__version__
    assert re.match(r"^\d+\.\d+\.\d+(-(alpha|beta|rc)\d*)?$", v), v
```

**Step 3: Run test — should fail (module missing)**

Run: `python run_tests.py tests/test_version.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError.

**Step 4: Create the file**

Write: `src/__version__.py`

```python
__version__ = "0.0.0-dev"
```

**Step 5: Run test — should pass**

Run: `python run_tests.py tests/test_version.py -v`
Expected: PASS.

**Step 6: Wire into `src/main.py`**

Near the top of `main()`:

```python
from __version__ import __version__
get_logger().info("WinScanLLM %s starting", __version__)
```

**Step 7: Commit**

```bash
git add src/__version__.py src/main.py tests/test_version.py
git commit -m "feat: Add version module and log version at startup"
```

---

## Task 2: Generate and commit `assets/icon.ico`

**Files:**
- Create: `assets/icon.ico` (binary, checked in)
- Create: `scripts/generate_ico.py` (one-time generator, committed for reproducibility)

**Step 1: Write the generator script**

Create: `scripts/generate_ico.py`

```python
"""One-time: generate assets/icon.ico from assets/icon.png.
Run manually when icon.png changes. The .ico is committed; not a build step."""
from pathlib import Path
from PIL import Image

SRC = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
DST = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

def main() -> None:
    img = Image.open(SRC).convert("RGBA")
    img.save(DST, format="ICO", sizes=SIZES)
    print(f"Wrote {DST}")

if __name__ == "__main__":
    main()
```

**Step 2: Run the generator**

Run: `python scripts/generate_ico.py`
Expected: `assets/icon.ico` created; file size several KB to tens of KB.

**Step 3: Sanity check**

Run: `python -c "from PIL import Image; im = Image.open('assets/icon.ico'); print(im.size, im.format)"`
Expected: prints a size and `ICO`.

**Step 4: Commit**

```bash
git add assets/icon.ico scripts/generate_ico.py
git commit -m "build: Add multi-resolution icon.ico for installer and exe"
```

---

## Task 3: `UpdateService` scaffolding + version comparison (TDD)

**Files:**
- Create: `src/services/update_service.py`
- Create: `tests/services/test_update_service.py`

**Step 1: Write failing tests for version comparison**

Create: `tests/services/test_update_service.py`

```python
from dataclasses import dataclass
import pytest
from services.update_service import decide_update, UpdateInfo

@dataclass
class FakeRelease:
    tag_name: str
    prerelease: bool = False
    assets: list[dict] = None

def test_newer_tag_triggers_update():
    r = FakeRelease(tag_name="v1.2.3")
    info = decide_update(current="1.0.0", release=r, include_prereleases=False, skipped="")
    assert info is not None
    assert info.version == "1.2.3"

def test_same_tag_no_update():
    r = FakeRelease(tag_name="v1.0.0")
    assert decide_update("1.0.0", r, False, "") is None

def test_older_tag_no_update():
    r = FakeRelease(tag_name="v0.9.0")
    assert decide_update("1.0.0", r, False, "") is None

def test_prerelease_filtered_by_default():
    r = FakeRelease(tag_name="v1.2.3-rc1", prerelease=True)
    assert decide_update("1.0.0", r, include_prereleases=False, skipped="") is None

def test_prerelease_allowed_when_opted_in():
    r = FakeRelease(tag_name="v1.2.3-rc1", prerelease=True)
    info = decide_update("1.0.0", r, include_prereleases=True, skipped="")
    assert info is not None

def test_skipped_version_is_respected():
    r = FakeRelease(tag_name="v1.2.3")
    assert decide_update("1.0.0", r, False, skipped="v1.2.3") is None
```

**Step 2: Run — all fail**

Run: `python run_tests.py tests/services/test_update_service.py -v`
Expected: 6 FAIL (module doesn't exist).

**Step 3: Write minimal implementation**

Create: `src/services/update_service.py`

```python
from dataclasses import dataclass
from typing import Any, Protocol
from packaging.version import Version, InvalidVersion

@dataclass(frozen=True)
class UpdateInfo:
    version: str
    asset_url: str
    asset_digest: str | None  # "sha256:..."
    asset_size: int

class _ReleaseLike(Protocol):
    tag_name: str
    prerelease: bool
    assets: list[dict[str, Any]] | None

def _strip_v(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag

def decide_update(
    current: str,
    release: _ReleaseLike,
    include_prereleases: bool,
    skipped: str,
) -> UpdateInfo | None:
    if release.tag_name == skipped:
        return None
    if release.prerelease and not include_prereleases:
        return None
    try:
        cur = Version(current)
        new = Version(_strip_v(release.tag_name))
    except InvalidVersion:
        return None
    if new <= cur:
        return None
    # assets may be None in test fakes
    asset = _find_installer_asset(release.assets or [])
    return UpdateInfo(
        version=_strip_v(release.tag_name),
        asset_url=asset.get("browser_download_url", "") if asset else "",
        asset_digest=asset.get("digest") if asset else None,
        asset_size=int(asset.get("size", 0)) if asset else 0,
    )

def _find_installer_asset(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for a in assets:
        name = a.get("name", "")
        if name.startswith("WinScanLLM-Setup-") and name.endswith(".exe"):
            return a
    return None
```

**Step 4: Run — all pass**

Run: `python run_tests.py tests/services/test_update_service.py -v`
Expected: 6 PASS.

**Step 5: Commit**

```bash
git add src/services/update_service.py tests/services/test_update_service.py
git commit -m "feat: Add version-comparison core for UpdateService"
```

---

## Task 4: Cache short-circuit (TDD)

**Files:**
- Modify: `src/services/update_service.py` (add `load_cache`, `save_cache`, `should_check_now`)
- Modify: `tests/services/test_update_service.py`

**Step 1: Append failing tests**

```python
from datetime import datetime, timedelta, timezone
from services.update_service import should_check_now, CACHE_TTL

def test_cache_fresh_suppresses_check():
    last = datetime.now(timezone.utc) - timedelta(hours=1)
    assert should_check_now(last) is False

def test_cache_expired_allows_check():
    last = datetime.now(timezone.utc) - timedelta(hours=7)
    assert should_check_now(last) is True

def test_no_cache_allows_check():
    assert should_check_now(None) is True
```

**Step 2: Run — fail**

**Step 3: Implement in `update_service.py`**

```python
from datetime import datetime, timedelta, timezone

CACHE_TTL = timedelta(hours=6)

def should_check_now(last_checked_at: datetime | None) -> bool:
    if last_checked_at is None:
        return True
    return datetime.now(timezone.utc) - last_checked_at >= CACHE_TTL
```

**Step 4: Run — pass**

**Step 5: Commit**

```bash
git add -u
git commit -m "feat: Add 6-hour update-check cache TTL"
```

---

## Task 5: Redirect host allowlist (TDD)

**Files:**
- Modify: `src/services/update_service.py`
- Modify: `tests/services/test_update_service.py`

**Step 1: Append tests**

```python
from services.update_service import is_allowed_download_url

@pytest.mark.parametrize("url,ok", [
    ("https://github.com/foo/bar/releases/download/v1/file.exe", True),
    ("https://api.github.com/repos/foo/bar/releases/assets/123", True),
    ("https://objects.githubusercontent.com/...", True),
    ("https://evil.com/payload.exe", False),
    ("http://github.com/foo/bar/...", False),     # no TLS
    ("ftp://github.com/foo", False),
    ("", False),
])
def test_url_host_allowlist(url, ok):
    assert is_allowed_download_url(url) is ok
```

**Step 2: Run — fail**

**Step 3: Implement**

```python
from urllib.parse import urlparse

_ALLOWED_HOSTS = {
    "github.com",
    "api.github.com",
    "objects.githubusercontent.com",
}

def is_allowed_download_url(url: str) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    return p.scheme == "https" and p.hostname in _ALLOWED_HOSTS
```

**Step 4: Run — pass. Step 5: Commit.**

```bash
git add -u
git commit -m "feat: Host-allowlist update downloads to GitHub hosts only"
```

---

## Task 6: Download + SHA-256 verification (TDD)

**Files:**
- Modify: `src/services/update_service.py` (add `download_and_verify`)
- Modify: `tests/services/test_update_service.py`

**Step 1: Append tests (use `responses` or `requests_mock` — check which is already a dev dep; fall back to `monkeypatch`)**

```python
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock
from services.update_service import download_and_verify, DownloadError

def _fake_response(body: bytes):
    m = MagicMock()
    m.iter_content = lambda chunk_size: [body]
    m.headers = {"content-length": str(len(body))}
    m.url = "https://objects.githubusercontent.com/payload.exe"
    m.raise_for_status = MagicMock()
    return m

def test_download_verifies_hash_and_returns_path(tmp_path):
    body = b"installer bytes"
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    with patch("services.update_service.requests.get", return_value=_fake_response(body)):
        out = download_and_verify(
            url="https://github.com/foo/bar/releases/download/v1/WinScanLLM-Setup-1.0.0.exe",
            expected_digest=digest,
            dest_dir=tmp_path,
        )
    assert out.exists()
    assert out.read_bytes() == body

def test_download_rejects_hash_mismatch(tmp_path):
    body = b"tampered"
    wrong_digest = "sha256:" + hashlib.sha256(b"original").hexdigest()
    with patch("services.update_service.requests.get", return_value=_fake_response(body)):
        with pytest.raises(DownloadError, match="hash"):
            download_and_verify(
                url="https://github.com/foo/bar/releases/download/v1/WinScanLLM-Setup-1.0.0.exe",
                expected_digest=wrong_digest,
                dest_dir=tmp_path,
            )
    # temp file cleaned up
    assert list(tmp_path.iterdir()) == []

def test_download_rejects_disallowed_host(tmp_path):
    with pytest.raises(DownloadError, match="host"):
        download_and_verify(
            url="https://evil.com/payload.exe",
            expected_digest="sha256:" + "0" * 64,
            dest_dir=tmp_path,
        )
```

**Step 2: Run — fail. Step 3: Implement.**

```python
import hashlib
import tempfile
from pathlib import Path
import requests

class DownloadError(Exception): ...

_USER_AGENT = "WinScanLLM-updater"  # wrapper fills actual version at runtime

def download_and_verify(
    url: str,
    expected_digest: str,
    dest_dir: Path,
    user_agent: str = _USER_AGENT,
    timeout: tuple[float, float] = (5.0, 30.0),
) -> Path:
    if not is_allowed_download_url(url):
        raise DownloadError(f"download host not allowed: {url}")
    if not expected_digest.startswith("sha256:"):
        raise DownloadError(f"unsupported digest: {expected_digest}")
    expected_hex = expected_digest.split(":", 1)[1].lower()

    dest_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".exe", dir=str(dest_dir))
    tmp_path = Path(tmp_name)
    try:
        import os
        os.close(fd)
        h = hashlib.sha256()
        with requests.get(url, headers={"User-Agent": user_agent},
                          stream=True, timeout=timeout, allow_redirects=True) as r:
            r.raise_for_status()
            if not is_allowed_download_url(r.url):
                raise DownloadError(f"redirect host not allowed: {r.url}")
            with tmp_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        h.update(chunk)
                        f.write(chunk)
        if h.hexdigest().lower() != expected_hex:
            raise DownloadError("downloaded file hash mismatch")
        return tmp_path
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
```

**Step 4: Run — pass. Step 5: Commit.**

```bash
git add -u
git commit -m "feat: Download + SHA-256 verify installer from GitHub Releases"
```

---

## Task 7: GitHub Releases API fetch (TDD with mocked `requests`)

**Files:**
- Modify: `src/services/update_service.py` (add `fetch_latest_release`)
- Modify: `tests/services/test_update_service.py`

**Step 1: Append test** that mocks `requests.get` returning a canned GitHub v2 release JSON. Assert it parses into a `_ReleaseLike` equivalent.

**Step 2: Implement** — straight `requests.get(f"https://api.github.com/repos/{owner}/{repo}/releases/latest", headers={"Accept":"application/vnd.github+json", "X-GitHub-Api-Version":"2022-11-28", "User-Agent": ua})`, return a simple dataclass `FetchedRelease(tag_name, prerelease, assets)`.

**Step 3: Commit.**

```bash
git add -u
git commit -m "feat: Fetch latest release metadata from GitHub API"
```

---

## Task 8: `UpdateService(QObject)` — Qt wrapper + background thread

**Files:**
- Modify: `src/services/update_service.py`
- Create: `tests/services/test_update_service_qt.py` (use `pytest-qt` if already installed; otherwise mock signals by hand with `pytest.raises(SignalEmitted)`)

**Step 1: Write test that fires `check_for_updates()` on a QThread and asserts `update_available` emits with the expected `UpdateInfo`**, using mocked `fetch_latest_release`.

**Step 2-5: Implement `UpdateService(QObject)`** wrapping the pure functions, with signals: `update_available`, `update_check_failed`, `download_progress`, `download_complete`, `download_failed`. Run `check_for_updates` via `QThreadPool.globalInstance().start(...)` or a dedicated `QThread` + worker. Commit.

```bash
git add -u
git commit -m "feat: Qt wrapper + threaded update-check for UpdateService"
```

---

## Task 9: Config `[Updates]` section defaults

**Files:**
- Modify: `src/config/config_manager.py` (in `_create_default_config`)
- Modify: `tests/config/test_config_manager.py` (add test)

**Step 1: Write failing test** that constructs a fresh `ConfigManager` and asserts:
- `config.get_bool("Updates", "check_on_startup", default=False) is True`
- `config.get_bool("Updates", "include_prereleases", default=True) is False`
- `config.get_setting("Updates", "skipped_version") == ""`

**Step 2: Run — fail. Step 3: Add to `_create_default_config`:**

```python
config["Updates"] = {
    "check_on_startup": "true",
    "include_prereleases": "false",
    "skipped_version": "",
    "last_check_iso": "",
    "last_known_version": "",
}
```

**Step 4: Pass. Step 5: Commit.**

```bash
git add -u
git commit -m "feat: Default [Updates] section in ConfigManager"
```

---

## Task 10: Settings UI — "Check for updates on startup" + "Check now"

**Files:**
- Modify: `src/ui/settings/settings_tab_general.py` (add checkbox + button to the existing General tab)
- Modify: `src/ui/settings/settings_change_tracker.py` (track the new checkbox)
- Modify: `src/ui/settings/settings_actions.py` (wire the "Check now" button)

**Step 1: Read the current General tab to find the right insertion point** (typically below the "Scan on startup" checkbox).

**Step 2: Add `QCheckBox("Check for updates on startup")` bound to `Updates.check_on_startup`** and a `QPushButton("Check now")` next to it.

**Step 3: Wire the button** to call `UpdateService.check_for_updates()` (forced, bypasses cache) and show a toast/status-bar message with the result.

**Step 4: Add a UI smoke test** in `tests/ui/settings/` that patches `UpdateService` and asserts the button click triggers `check_for_updates(force=True)`.

**Step 5: Commit.**

```bash
git add -u
git commit -m "feat: Settings UI for update-check preference + manual check"
```

---

## Task 11: `UpdateBanner` widget

**Files:**
- Create: `src/ui/update_banner.py` — small `QFrame` with label + `[Install update] [Remind me later] [Skip this version]` buttons, exposes signals `install_clicked`, `remind_clicked(info)`, `skip_clicked(info)`.
- Create: `tests/ui/test_update_banner.py`

**Step 1-5:** TDD the three button signals; style it to match existing banner patterns (search the codebase for existing notification banners first — e.g. `maybe_show_analyze_nudge_after_discovery`). Commit.

```bash
git add -u
git commit -m "feat: Add UpdateBanner widget for non-modal update prompts"
```

---

## Task 12: Wire UpdateService + banner into main window

**Files:**
- Modify: `src/main.py` (instantiate `UpdateService` after `_on_init_complete`, delay 10s via `QTimer.singleShot`)
- Modify: main window class (inject the banner at the top of the central layout)

**Step 1: Identify the main window class.** (From CLAUDE.md / memory it's `src/ui/gui.py` — verify with Grep.)

**Step 2: Add `UpdateBanner` to the main layout.** Hide by default.

**Step 3: Wire `UpdateService.update_available → banner.show_for(info)`.**

**Step 4: Wire banner signals:**
- `install_clicked` → `UpdateService.download_update(info)` then on `download_complete` → confirmation dialog → `launch_installer_and_quit`
- `remind_clicked` → just hide the banner (next startup shows it again because cache is separate)
- `skip_clicked(info)` → `config.set("Updates", "skipped_version", f"v{info.version}")` and hide

**Step 5: Manual smoke test:** set `Updates.last_known_version = "0.0.0"`, set `__version__` to a low value, run the app, confirm banner appears. Commit.

```bash
git add -u
git commit -m "feat: Wire UpdateService and UpdateBanner into main window"
```

---

## Task 13: PyInstaller spec

**Files:**
- Create: `installer/WinScanLLM.spec`

**Step 1: Write the spec** (starting from `pyi-makespec src/main.py --name WinScanLLM --windowed --icon=assets/icon.ico` and hand-editing). Must include:
- `datas=[('assets', 'assets')]` — bundle icons/gifs
- `hiddenimports` for any PyQt6 plugins we use (typically none needed beyond defaults)
- `console=False` (GUI app)
- onedir mode (default)

**Step 2: Local smoke test**

```powershell
.\venv\Scripts\Activate.ps1
pyinstaller installer/WinScanLLM.spec
.\dist\WinScanLLM\WinScanLLM.exe
```

Expected: app launches normally.

**Step 3: Commit**

```bash
git add installer/WinScanLLM.spec
git commit -m "build: Add PyInstaller spec for onedir Windows build"
```

---

## Task 14: Inno Setup script

**Files:**
- Create: `installer/WinScanLLM.iss`
- Create: `installer/.gitignore` (ignore `Output/`)

**Step 1: Generate a stable AppId GUID**

```powershell
[guid]::NewGuid().ToString("B").ToUpper()
```

Record it. This GUID lives in the `.iss` forever — never regenerate.

**Step 2: Write `WinScanLLM.iss`**

```ini
#define AppName "WinScanLLM"
#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{PASTE-GENERATED-GUID-HERE}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=aberrantCode
AppPublisherURL=https://github.com/aberrantCode/WinScanOllamaVision
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=admin
CloseApplications=force
RestartApplications=no
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
OutputDir=Output
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppName}.exe
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; WorkingDir: "{app}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  DeleteUserDataPage: TInputOptionWizardPage;

procedure InitializeUninstallProgressForm;
begin
  // Only prompt during interactive uninstall
  if not UninstallSilent then
  begin
    if MsgBox('Also delete your WinScanLLM user data (settings, databases, logs) in %APPDATA%\WinScanLLM?' + #13#10 + #13#10 +
              'Choose No to keep your data for a future reinstall.',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\WinScanLLM'), True, True, True);
    end;
  end;
end;
```

**Step 3: Create `installer/.gitignore`**

```
Output/
```

**Step 4: Commit**

```bash
git add installer/WinScanLLM.iss installer/.gitignore
git commit -m "build: Add Inno Setup script with upgrade and uninstall logic"
```

---

## Task 15: Local build script

**Files:**
- Create: `scripts/build-installer.ps1`

**Step 1: Write the script**

```powershell
param([string]$Version = "0.0.0-dev")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Set-Content "$root\src\__version__.py" "__version__ = `"$Version`"`n"
Push-Location $root
try {
    pyinstaller installer/WinScanLLM.spec
    $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) { throw "Inno Setup 6 not found at $iscc" }
    & $iscc /DAppVersion=$Version installer/WinScanLLM.iss
    Write-Host "Built: installer/Output/WinScanLLM-Setup-$Version.exe" -ForegroundColor Green
} finally {
    Pop-Location
}
```

**Step 2: Local smoke test**

```powershell
.\scripts\build-installer.ps1 -Version "0.1.0-dev"
.\installer\Output\WinScanLLM-Setup-0.1.0-dev.exe
```

Click through installer, confirm:
- [ ] Install creates `C:\Program Files\WinScanLLM\WinScanLLM.exe`
- [ ] Desktop icon present and launches app
- [ ] Start Menu entry present
- [ ] Add/Remove Programs shows "WinScanLLM 0.1.0-dev" with our icon
- [ ] Uninstall prompts about user data
- [ ] After uninstall, `C:\Program Files\WinScanLLM` is gone; `%APPDATA%\WinScanLLM` preserved (if "No" was chosen)

**Step 3: Commit**

```bash
git add scripts/build-installer.ps1
git commit -m "build: Add local PowerShell installer-build script"
```

---

## Task 16: Rework `.github/workflows/release.yml`

**Files:**
- Modify: `.github/workflows/release.yml`

**Step 1: Replace the entire `build-executables` matrix job with the `build-windows-installer` job** described in Section D.1 of the design doc. Also remove the `pip install + twine upload` PyPI publish step from `create-release`.

**Step 2: Add the `smoke-test-installer` job** described in Section E.2 of the design doc.

**Step 3: Dry-run validation**

```powershell
# Install act (GitHub Actions local runner) OR just push a tag to a fork
# For lightweight validation, at minimum:
Get-Content .github/workflows/release.yml | yamllint -
```

**Step 4: Commit**

```bash
git add -u
git commit -m "ci: Build Windows installer on release tag and smoke-test it"
```

---

## Task 17: README updates

**Files:**
- Modify: `README.md` (installation section + SmartScreen note + update behavior)

**Step 1: Add an "Installation (end users)" section** that points to the latest GitHub Release, explains the SmartScreen warning and how to bypass it, and documents the default update behavior.

**Step 2: Commit.**

```bash
git add README.md
git commit -m "docs: End-user install instructions and update behavior"
```

---

## Task 18: End-to-end release dry-run on a fork

**Manual QA step, no commit.**

1. Fork the repo to a disposable test location OR create a branch-based release.
2. Tag `v0.1.0-dryrun` on `feat/windows-installer`.
3. Wait for the `release.yml` run to complete.
4. Download `WinScanLLM-Setup-0.1.0-dryrun.exe` from the release.
5. On a clean Win11 VM (or fresh user profile):
   - [ ] Installer runs, creates desktop icon, Start Menu entry
   - [ ] App launches; version in logs reads `0.1.0-dryrun`
   - [ ] Publish `v0.1.1-dryrun` with a trivial change; the older install shows the update banner within 20s of startup
   - [ ] Click "Install update": UAC prompt, app closes, new installer runs, app relaunches as `v0.1.1-dryrun`
   - [ ] Uninstall interactively, choose "Yes, delete user data"
   - [ ] `%APPDATA%\WinScanLLM` gone, `C:\Program Files\WinScanLLM` gone
6. Delete the dry-run tags and their releases.

---

## Task 19: Open PR to `dev`

**Final step.**

```bash
# Rebase onto latest dev
git fetch origin
git rebase origin/dev
# Push
git push --force-with-lease
# Open PR
gh pr create --base dev --title "feat: Windows installer with self-update" --body "$(cat <<'EOF'
## Summary
- PyInstaller (onedir) + Inno Setup 6 produce `WinScanLLM-Setup-<ver>.exe`
- `UpdateService` polls GitHub Releases, verifies SHA-256, hands off to Inno Setup with `/SILENT`
- Per-machine install to `Program Files\WinScanLLM`; user data in `%APPDATA%\WinScanLLM` preserved across upgrades
- Desktop icon + Start Menu entry created by installer
- CI builds the installer and runs a silent install/uninstall smoke test on tagged releases
- Design doc: docs/plans/2026-04-22-windows-installer-design.md

## Test Plan
- [ ] `python run_tests.py tests/ -v` all pass
- [ ] `python run_tests.py tests/services/test_update_service.py -v` full coverage of decide_update / download_and_verify / host allowlist
- [ ] `scripts/build-installer.ps1 -Version 0.1.0-dev` produces working installer locally
- [ ] Installer creates desktop icon, Start Menu entry, Add/Remove Programs entry
- [ ] Upgrade path preserves %APPDATA% data
- [ ] Uninstall default keeps user data; "Yes, delete" clears %APPDATA%
- [ ] End-to-end dry-run release (Task 18) passed
EOF
)"
```

---

## Post-merge: cut `v0.1.0`

1. Merge PR.
2. `git checkout dev && git pull`.
3. `git tag v0.1.0 && git push --tags`.
4. `release.yml` produces the real `WinScanLLM-Setup-0.1.0.exe`.
5. Test auto-update from an internally-distributed `v0.0.9` pre-release (if any users are on it) or skip — `v0.1.0` is the first public installer.

---

## Task dependency graph

```
Task 0 (run_tests.py fix) ──→ Task 1 (version file)
                              │
                              ├──→ Task 2 (icon.ico)
                              │
                              └──→ Task 3 (UpdateService core)
                                    │
                                    ├──→ Task 4 (cache TTL)
                                    ├──→ Task 5 (host allowlist)
                                    ├──→ Task 6 (download + verify)
                                    ├──→ Task 7 (GitHub API fetch)
                                    └──→ Task 8 (Qt wrapper)
                                          │
                                          ├──→ Task 9 (config defaults)
                                          │     │
                                          │     └──→ Task 10 (settings UI)
                                          │
                                          └──→ Task 11 (banner)
                                                │
                                                └──→ Task 12 (wire into main)
                                                      │
                                                      └──→ Task 13 (PyInstaller spec)
                                                            │
                                                            └──→ Task 14 (Inno Setup)
                                                                  │
                                                                  └──→ Task 15 (build script)
                                                                        │
                                                                        └──→ Task 16 (CI rework)
                                                                              │
                                                                              └──→ Task 17 (README)
                                                                                    │
                                                                                    └──→ Task 18 (dry-run)
                                                                                          │
                                                                                          └──→ Task 19 (PR)
```

Tasks 2, 4, 5, 6, 7 can be parallelized (all modify `src/services/update_service.py` independently); the rest are essentially linear.
