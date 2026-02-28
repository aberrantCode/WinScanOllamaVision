# pipeline_window.py — Code Review Checklist

Source file: `src/ui/pipeline_window.py`
Review date: 2026-02-19

---

## CRITICAL

### [C1] Replace `subprocess.Popen` with `os.startfile` — line 1403

- [x] Remove `subprocess.Popen(["explorer", output_dir])`
- [x] Replace with `os.startfile(output_dir)`
- [x] Remove `import subprocess` from inside the method (line 1398)

**Why:** `Popen` leaks the process handle — it is never closed. `os.startfile` is the idiomatic Windows API for opening Explorer and eliminates the subprocess entirely.

---

### [C2] Log directory loading failures instead of swallowing them — lines 486-487

- [x] Replace bare `except Exception: pass` in `_populate_directory_combo`
- [x] Add logging:
  ```python
  except Exception as e:
      _get_logger().error("[ImportPanel] Failed to load directories: %s", e, exc_info=True)
  ```

**Why:** Silent failures leave the user with an empty combo box and no diagnostic information.

---

## HIGH

### [H1] Debounce `_on_file_status_changed` to avoid full DB reload per file — lines 1020-1022

- [x] Add a `QTimer` debounce (500 ms) in `AnalyzePanel.__init__`
- [x] Replace the direct `refresh()` call in `_on_file_status_changed` with `timer.start()` (restarts the timer on each call)
- [x] Connect the timer's `timeout` signal to `refresh()`

**Why:** 500 files in analysis = 500 full DB queries + grid rebuilds back-to-back. A debounce collapses rapid successive signals into a single refresh.

---

### [H2] Add stage bounds checking — lines 1553, 1571-1575

- [x] In `_on_back_clicked`: clamp result with `stage = max(STAGE_IMPORT, stage - 1)`
- [x] In `_on_next_clicked`: clamp result with `stage = min(STAGE_EXPORT, stage + 1)`
- [x] Clamp the value received from the header's `stage_clicked` signal before passing to `_go_to_stage`

**Why:** Without clamping, it is possible to navigate to stage `-1` or stage `4`, which are out of bounds for the `QStackedWidget`.

---

### [H3] Replace dead `AnalyzePanel.closeEvent` with explicit `shutdown()` — lines 1122-1126

- [x] Remove `closeEvent` override from `AnalyzePanel` (embedded `QWidget`s never receive it)
- [x] Add a public `shutdown(self) -> None` method that stops/waits on the worker
- [x] Call `self.analyze_panel.shutdown()` from `DocumentPipelineWindow.closeEvent`

**Why:** `closeEvent` on an embedded widget never fires, so the worker cleanup is dead code and the worker can outlive the window.

---

### [H4] Unify `dark_mode` / `is_dark_mode` into a single attribute — lines 699-701

- [x] Identify all reads of both `dark_mode` and `is_dark_mode` in `AnalyzePanel`
- [x] Settle on one name (e.g. `dark_mode` to match other panels)
- [x] Remove the duplicate attribute; expose the single one as a `@property` if theme switching must propagate
- [x] Verify `FileDetailsGrid` and `AnalyzePanel._c()` both use the same source of truth

**Why:** If theme switching updates one attribute but not the other, colour lookups across the class will disagree silently.

---

### [H5] Reset `_stats` at the start of each analysis run — lines 1082-1086

- [x] In `AnalyzePanel._on_start()`, add `self._stats = {"analyzed": 0, "cached": 0, "errors": 0, "total_files": 0}` before starting the worker

**Why:** `_stats` is accumulated with `+=` but never zeroed. Running analysis twice inflates totals, producing misleading progress and summary numbers.

---

### [H6] Type `file_grid` as `FileDetailsGrid | None` — line 719

- [x] Change annotation from `file_grid: Any | None = None` to `file_grid: FileDetailsGrid | None = None`
- [x] Add `FileDetailsGrid` under a `TYPE_CHECKING` guard import at the top of the file if not already present

**Why:** `Any` silently disables all mypy type-checking for every access to `file_grid`.

---

## MEDIUM

### [M1] Do not call private `_refresh()` from parent — line 1565

- [x] Add a public `refresh(self) -> None` method to `ImportPanel` that delegates to `_refresh`
- [x] Update the call site in `DocumentPipelineWindow` to use `import_panel.refresh()`

---

### [M2] Do not access `analyze_panel._worker` from parent — lines 1602-1604

- [x] Add a public `is_running(self) -> bool` property (or `abort()` method) to `AnalyzePanel`
- [x] Update `DocumentPipelineWindow` to use the public API

---

### [M3] Extract shared `_divider()` helper — lines 664, 1129, 1309, 1410

- [x] Create a module-level (or mixin) helper `_make_divider(color: str) -> QFrame`
- [x] Replace the four copy-pasted implementations with calls to the shared helper

---

### [M4] Extract shared `link_style` constant — lines 342, 809

- [x] Define `_LINK_STYLE` as a module-level constant using `{0}` format instead of `%s`
- [x] Replace both usage sites

---

### [M5] Remove duplicate `contextlib` import inside `update_stats` — line 1381

- [x] Delete the `import contextlib` statement inside the method body
- [x] Confirm the top-level `import contextlib` (line 9) covers it

---

### [M6] Remove `import subprocess` inside method — line 1398

- [x] Covered by C1 (`os.startfile` replaces the subprocess entirely); verify no other `subprocess` use remains

---

### [M7] Move `from datetime import datetime` to top-level imports — lines 497, 881

- [x] Add `from datetime import datetime` with the other imports at the top of the file
- [x] Remove the two inline import statements inside method bodies

---

### [M8] Replace `assert` runtime guards with proper checks — lines 365, 1269

- [x] Replace `assert widget is not None` (or equivalent) with an explicit `if widget is None: return` (or `raise`)
- [x] `assert` statements are stripped when Python is run with the `-O` flag

---

### [M9] Add timezone to `datetime.fromtimestamp()` calls — lines 525, 915

- [x] Change `datetime.fromtimestamp(mtime)` to `datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)` (or local tz)
- [x] Update any formatting that depends on the result

---

## LOW

### [L1] Define magic numbers as class constants — lines 124, 178

- [x] Replace magic numbers `76`, `26`, `8` (repeated column widths / row heights) with named class-level constants

---

### [L2] Cache `ImageFilesRepository` instead of re-instantiating per call — lines 502, 641, 650

- [x] Create `self._image_repo: ImageFilesRepository` once in `__init__`
- [x] Replace the three inline `ImageFilesRepository(self.analysis_db.connection)` calls with `self._image_repo`

---

### [L3] Standardise the module-level logger pattern — lines 51-66

- [x] Replace the global mutable logger + `TYPE_CHECKING` guard with the project-standard `get_logger()` call at point of use (matches the rest of the codebase)

---

### [L4] Split `pipeline_window.py` into a `pipeline/` subpackage — 1612 lines

- [x] Extract `ImportPanel` → `pipeline/import_panel.py`
- [x] Extract `AnalyzePanel` → `pipeline/analyze_panel.py`
- [x] Extract `BundlePanel` → `pipeline/bundle_panel.py`
- [x] Extract `ExportPanel` → `pipeline/export_panel.py`
- [x] Keep `DocumentPipelineWindow` in `pipeline/window.py` (or `pipeline/__init__.py`)
- [x] Update all import sites

**Why:** Project guideline is 800 lines max. At 1612 lines the file is already twice that.

---

### [L5] Type `_embedded_workflow` properly — line 1169

- [x] Replace `_embedded_workflow: Any | None` with the concrete type under a `TYPE_CHECKING` guard

---

## Summary

| Priority | Count | Status |
|----------|-------|--------|
| Critical | 2 | ☑ ☑ |
| High | 6 | ☑ ☑ ☑ ☑ ☑ ☑ |
| Medium | 9 | ☑ ☑ ☑ ☑ ☑ ☑ ☑ ☑ ☑ |
| Low | 5 | ☑ ☑ ☑ ☑ ☑ |
