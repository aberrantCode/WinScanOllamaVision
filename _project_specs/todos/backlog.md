# Backlog

Future work, prioritized. Move to `active.md` when starting.

---

## Testing: Increase test coverage to >80%

**Objective:** Add comprehensive unit and integration tests for all modules

**Validation:**
- [ ] Coverage report shows >80% across all `src/` modules
- [ ] All providers have mocked integration tests
- [ ] GUI components have basic smoke tests
- [ ] Database operations have transaction tests

---

## Feature: Add PDF batch processing support

**Objective:** Support multi-page PDF analysis in addition to image files

**Validation:**
- [ ] PDF files detected in scan directories
- [ ] Extract pages as images for LLM analysis
- [ ] Maintain page order and document structure
- [ ] Progress tracking for PDF processing

---

## Optimization: Parallel LLM analysis for batch processing

**Objective:** Process multiple images concurrently to improve throughput

**Validation:**
- [ ] Configurable worker pool size
- [ ] Thread-safe database writes
- [ ] Progress tracking with concurrent operations
- [ ] Graceful error handling per-worker

---

## Testing: Restore full-suite green + 90% coverage gate on pre-push

**Context:** CI moved from GitHub Actions to a local gate (`scripts/verify.py`).
The pre-push hook runs the **quick** gate (ruff + mypy + curated fast test
subset, `--no-cov`). The **full** gate (`scripts/verify.ps1`) runs the whole
suite with `--no-cov` because `pytest tests/` is not yet green end-to-end and
total coverage sits at ~21% when only part of the suite runs.

**Objective:** Get the full suite green, then re-enable the coverage floor.

**Validation:**
- [ ] `python run_tests.py tests/` passes with no collection errors or failures
- [ ] UI/GUI/integration suites pass reliably (no LoggingService init races)
- [ ] Restore `--cov-fail-under=90` enforcement in the full gate
- [ ] Promote the full test suite into the pre-push hook (replace the subset)

---

<!-- Add new backlog items above this line -->
