# Windows Installer & Self-Update — Design

**Date:** 2026-04-22
**Status:** Approved (brainstorming phase) — awaiting implementation plan
**Branch:** `fix/ci-hygiene` (design only; implementation will branch off `dev`)

## Goal

Ship WinScanLLM to Windows workstations with:
1. A real Windows installer (deploy)
2. Automatic upgrade detection and installation from new releases
3. A clean uninstaller registered with Windows Apps & Features
4. A desktop icon that launches the application

## Decisions

| Axis | Decision |
|---|---|
| Update UX | App self-updates (checks on startup, downloads, launches new installer) |
| Install scope | Per-machine (`C:\Program Files\WinScanLLM`), UAC required |
| Code signing | Ship unsigned for now; script built so a cert can be added later without restructuring |
| Update channel | Public GitHub Releases on `aberrantCode/WinScanOllamaVision` |
| Installer tech | Inno Setup 6 |
| Packaging | PyInstaller onedir (not onefile), wrapped by Inno Setup |
| Executable rename | `WinScanOllamaVision.exe` → `WinScanLLM.exe` |

## Architectural anchor

The app writes **all** user data to `%APPDATA%\WinScanLLM\` (settings, databases, logs). Program files and user data are fully separated. Therefore:

- Upgrades can freely blow away and replace the install directory — user data is untouched.
- Uninstall can default to preserving user data, with an opt-in prompt to also wipe `%APPDATA%`.
- No migration code is ever needed when the schema inside `%APPDATA%` changes across releases.

## Section A — Packaging & installer layout

### A.1 Packaging (PyInstaller)

- **New file:** `installer/WinScanLLM.spec` (checked in). Replaces the ad-hoc `pyinstaller --onefile --windowed ...` CLI in `release.yml`.
- **Onedir mode.** Faster startup, less AV friction; single-file advantage disappears because Inno Setup wraps the whole folder anyway.
- **Icon:** generate `assets/icon.ico` (16/32/48/256 multi-res) from `assets/icon.png` once via Pillow and check in. PyInstaller embeds via `--icon=assets/icon.ico`.
- **Executable name:** `WinScanLLM.exe`.

### A.2 Inno Setup script

- **New file:** `installer/WinScanLLM.iss`.
- `AppId={{B7F4E8A2-...}}` — **stable GUID**, generated once, never changed. Required for upgrade detection.
- `AppName=WinScanLLM`, `AppPublisher`, `AppPublisherURL`.
- `AppVersion` injected at build time via `iscc /DAppVersion=<version>`.
- `PrivilegesRequired=admin`.
- `DefaultDirName={autopf}\WinScanLLM`.
- `CloseApplications=force`, `RestartApplications=no` (we relaunch ourselves in `[Run]`).
- `OutputBaseFilename=WinScanLLM-Setup-{#AppVersion}`.
- `UninstallDisplayIcon={app}\WinScanLLM.exe`.

### A.3 Shortcuts

`[Tasks]` entry `desktopicon` (checked by default).

`[Icons]`:
- `{commondesktop}\WinScanLLM` → `{app}\WinScanLLM.exe` (all users)
- `{commonprograms}\WinScanLLM` → Start Menu entry (all users)

Both shortcuts use the bundled `.ico` and set working dir to `{app}`.

## Section B — Self-update flow

### B.1 New module

`src/services/update_service.py` — `UpdateService(QObject)`:

```python
class UpdateService(QObject):
    update_available = pyqtSignal(UpdateInfo)
    update_check_failed = pyqtSignal(str)
    download_progress = pyqtSignal(int, int)
    download_complete = pyqtSignal(Path)
    download_failed = pyqtSignal(str)

    def check_for_updates(self) -> None: ...
    def download_update(self, info: UpdateInfo) -> None: ...
    def launch_installer_and_quit(self, setup_path: Path) -> None: ...
```

All I/O runs on a background `QThread`. UI never blocks.

### B.2 Version source

- `src/__version__.py` — single source of truth, written by CI from `GITHUB_REF_NAME`.
- Compare current vs `tag_name` using `packaging.version.Version`.
- Pre-releases (`-rc`, `-alpha`, `-beta`) skipped by default; hidden INI `[Updates] include_prereleases=true` opts in.

### B.3 Check cadence

- On startup: 10s after UI ready (avoids competing with initial scan).
- Manual: "Check for updates now" button in Settings → General.
- Cache at `%APPDATA%\WinScanLLM\update_cache.json`. Suppress re-checks within 6 hours. Respects GitHub's 60 req/hr unauthenticated limit.
- User setting: `[Updates] check_on_startup` (default `true`), exposed in Settings UI.

### B.4 UI

Non-modal banner at top of main window:
> Update available: v1.2.3 → v1.3.0  [Install update] [Remind me later] [Skip this version]

"Skip this version" stores the tag in `[Updates] skipped_version`; banner suppressed for that tag.

### B.5 Download & integrity

- Asset: `WinScanLLM-Setup-<version>.exe` from the release's asset list.
- Download target: `%LocalAppData%\Temp\WinScanLLM_update_<version>.exe`.
- Streaming `requests.get(..., timeout=(5, 30), stream=True)`.
- **SHA-256 verification** against the asset's `digest` field from GitHub Releases v2 API. Fail closed: mismatch → delete file, surface "Update failed verification" banner, no auto-retry.

### B.6 Handoff to installer

On user confirm:
1. `subprocess.Popen([setup_exe, "/SILENT", "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS", "/LOG=%TEMP%\\WinScanLLM_install.log"], creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS)`.
2. UAC prompt appears.
3. `QApplication.quit()`.
4. Inno Setup replaces files, then `[Run]` section launches new `WinScanLLM.exe`.

### B.7 Security

- `User-Agent: WinScanLLM/<version> (+https://github.com/aberrantCode/WinScanOllamaVision)`.
- Redirect host allowlist: `api.github.com`, `github.com`, `objects.githubusercontent.com`. Other redirect targets refused.
- No secrets in app (public API only).
- No rename-before-verify (hash computed on the downloaded path directly).

### B.8 Failure matrix

| Failure | Behavior |
|---|---|
| No internet | Silent. Next check in 6h. |
| GitHub 4xx/5xx | Silent + debug log. Retry next startup. |
| Hash mismatch | ERROR log, delete file, banner shows "Update failed verification". No auto-retry. |
| UAC denied | Installer never runs. Banner reappears on next launch. |
| Installer exit != 0 | App already quit. User sees setup's own error. Banner reappears. |

## Section C — Uninstall

### C.1 Default behavior

- `unins000.exe` registered in **Settings → Apps** and legacy Add/Remove Programs.
- Removes: install directory, desktop shortcut, Start Menu entry, registry uninstall keys.
- **Does NOT touch** `%APPDATA%\WinScanLLM`.

### C.2 Optional data-removal prompt

`[Code]` section runs in `usUninstall` step **only** when `UninstallSilent=false` (i.e. interactive, not during an upgrade's silent self-uninstall):

> Also delete your WinScanLLM user data (settings, databases, logs) in `%APPDATA%\WinScanLLM`?
> Choose **No** to keep your data for a future reinstall.
> `[ Yes ]  [ No — default ]`

### C.3 Out of scope for uninstall

- Ollama / Claude CLI / Gemini CLI (external, shared with other tools).
- User-chosen source directories (not ours to manage).

## Section D — CI wiring

### D.1 New job in `.github/workflows/release.yml`

Replace the `build-executables` matrix with a single `build-windows-installer` job on `windows-latest`:

1. Checkout + Python 3.12 setup.
2. `pip install -r requirements.txt pyinstaller`.
3. Write `src/__version__.py` from `${{ github.ref_name }}` (strip `v`).
4. `pyinstaller installer/WinScanLLM.spec`.
5. Run Inno Setup: `& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=$ver installer/WinScanLLM.iss` (Inno 6 is pre-installed on `windows-latest`).
6. Compute SHA-256: `Get-FileHash ... -Algorithm SHA256`.
7. Attach `WinScanLLM-Setup-<ver>.exe` and `.sha256` to the release via `softprops/action-gh-release@v2`.

### D.2 Removed from `release.yml`

- PyPI publish step (this is an application, not a library).
- Linux/macOS PyInstaller matrix (out of scope).

### D.3 Preserved

- `create-release` job (tag → release + changelog).
- Trigger `push.tags: v*.*.*`.

### D.4 Local developer build

`scripts/build-installer.ps1`:
```powershell
param([string]$Version = "0.0.0-dev")
Set-Content src/__version__.py "__version__ = `"$Version`""
pyinstaller installer/WinScanLLM.spec
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=$Version installer/WinScanLLM.iss
```

## Section E — Testing

### E.1 Unit tests

`tests/services/test_update_service.py` — covers:
- GitHub API response: newer / same / older / pre-release tag → correct decision
- 6h cache short-circuit (no network on second call within window)
- `include_prereleases=false` filters out non-stable tags
- `skipped_version` suppresses banner for that tag
- Download hash mismatch → cleanup, no retry
- Download hash match → `download_complete(path)`
- Redirect host allowlist refuses non-GitHub hosts

`tests/installer/test_version_file.py` — sanity checks `src/__version__.py`.

### E.2 CI smoke test

`smoke-test-installer` job (same workflow):
1. `Setup.exe /VERYSILENT /NORESTART /LOG=install.log`
2. Assert `C:\Program Files\WinScanLLM\WinScanLLM.exe` exists and `unins000.exe` exists
3. `unins000.exe /VERYSILENT`
4. Assert `C:\Program Files\WinScanLLM` is gone

### E.3 Manual test plan (per release)

On clean Win11 VM:
- [ ] Fresh install → desktop icon present, Start Menu present, app launches
- [ ] Upgrade install → old version gone, user data preserved, new version launches
- [ ] Self-update path: banner appears, install completes, app relaunches as new version
- [ ] Interactive uninstall → prompt appears, default No preserves `%APPDATA%`
- [ ] Uninstall with "Yes, delete data" → `%APPDATA%\WinScanLLM` gone
- [ ] SmartScreen warning documented in README

## Non-goals / YAGNI

| Excluded | Why |
|---|---|
| Code signing | Budget decision; scripted so a cert can drop in later |
| Per-user install | Ruled out by install-scope decision |
| MSI / WiX | Inno Setup covers per-machine single-app install |
| macOS / Linux installers | Not requested |
| Bundling Ollama/Claude/Gemini CLIs | External deps; users install separately |
| Delta/patching updates | Full-installer replacement is fast enough |
| Rollback-on-failure | User can re-download prior installer from GH Releases |
| Multiple update channels (stable/beta UI) | Hidden flag only |

## Files that will change

**New:**
- `installer/WinScanLLM.spec`
- `installer/WinScanLLM.iss`
- `assets/icon.ico`
- `src/__version__.py`
- `src/services/update_service.py`
- `scripts/build-installer.ps1`
- `tests/services/test_update_service.py`
- `tests/installer/test_version_file.py`

**Modified:**
- `.github/workflows/release.yml` (rework Windows job, drop others)
- `src/main.py` (wire UpdateService on startup)
- `src/ui/main_window.py` (update banner) — or equivalent
- `src/config/config_manager.py` (register `[Updates]` section defaults)
- One of the Settings tabs (expose "Check for updates on startup" toggle + manual check button)
- `requirements.txt` (add `packaging` as explicit dep if not already pulled)
- `README.md` (install/uninstall instructions, SmartScreen note)

## Next step

Hand off to `superpowers:writing-plans` for an implementation plan with phases, task ordering, and review checkpoints.
