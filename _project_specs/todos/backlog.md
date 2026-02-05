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

<!-- Add new backlog items above this line -->
