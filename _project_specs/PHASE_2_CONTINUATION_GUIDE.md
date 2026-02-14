# Exception Handling Refactoring - Phase 2 Continuation Guide

**Last Updated:** 2026-02-12
**Branch:** `refactor/exception-handling-comprehensive`
**Session Status:** Phase 1 Complete, Phase 2.1 Partial (8/31 commits)

---

## ✅ Completed Work Summary

### Phase 1: COMPLETE (11 critical tasks, 8 commits)
- All file hash, AppData, logging, database, network operations hardened
- TDD methodology (RED-GREEN-REFACTOR) with 95%+ test coverage
- All tests passing, type checking clean

### Phase 2.1: PARTIAL (8/31 commits complete, 1 commit)
**Completed repositories:**
- ✅ audit_repo.py (1 commit wrapped)
- ✅ directory_repo.py (3 commits wrapped)
- ✅ bundle_images_repo.py (4 commits wrapped)

**Commit:** `ddec664` - "feat: add exception handling to repository commits (phase 2.1 - partial)"

---

## 🔧 Phase 2.1: Complete Repository Commit Wrapping

### Remaining: 23 commits across 7 files

### Standard Pattern to Apply

```python
# Add to top of each file (if not present):
import sqlite3
from services.logging_service import get_logger

logger = get_logger()

# Wrap each self.conn.commit():
try:
    self.conn.commit()
except sqlite3.OperationalError as e:
    logger.error(f"[REPO NAME] Database locked: {e}")
    self.conn.rollback()
    raise sqlite3.OperationalError("Database is locked. Try again.") from e
except sqlite3.Error as e:
    logger.error(f"[REPO NAME] Database error: {e}")
    self.conn.rollback()
    raise sqlite3.Error(f"Failed to save changes: {e}") from e
```

### File-by-File Checklist

#### 1. bundle_repo.py (3 commits)
- [ ] Line 63 - wrap commit
- [ ] Line 110 - wrap commit
- [ ] Line 135 - wrap commit
- **Note:** Imports already added (from WIP), just wrap commits
- **Log prefix:** `[BUNDLE REPO]`

#### 2. image_files_repo.py (7 commits) ⚠️ Largest file
- [ ] Line 57 - register()
- [ ] Line 137 - update_status()
- [ ] Line 154 - update_rotation()
- [ ] Line 172 - update_output_filename()
- [ ] Line 189 - clear_output_filename()
- [ ] Line 215 - update_hash()
- [ ] Line 260 - delete_by_path()
- [ ] Line 285 - update_hash_for_path()
- **Note:** Needs imports added first
- **Log prefix:** `[IMAGE FILES REPO]`

#### 3. metadata_repo.py (4 commits)
- [ ] Line 69 - create_from_analysis()
- [ ] Line 122 - update()
- [ ] Line 194 - archive()
- [ ] Line 268 - delete_for_image()
- **Note:** Logger started (from WIP), needs sqlite3 import
- **Log prefix:** `[METADATA REPO]`

#### 4. pdf_files_repo.py (3 commits)
- [ ] Line 66 - register()
- [ ] Line 118 - update_status()
- [ ] Line 142 - delete() ⚠️ Inside loop, be careful
- **Note:** Needs imports added
- **Log prefix:** `[PDF FILES REPO]`

#### 5. pdf_image_pages_repo.py (3 commits)
- [ ] Line 43 - link_page()
- [ ] Line 105 - update_page_number()
- [ ] Line 118 - delete_for_pdf()
- **Note:** Needs imports added
- **Log prefix:** `[PDF IMAGE PAGES REPO]`

#### 6. analysis_repo.py (1 commit)
- [ ] Line 248 - delete_by_image_file_id()
- **Note:** All imports already present from Phase 1, Task #8
- **Log prefix:** `[ANALYSIS REPO]`

#### 7. archived_metadata_repo.py (2 commits) 📝
- [ ] Line 48
- [ ] Line 81
- **Note:** Check if file exists, may have been missed in original count
- **Log prefix:** `[ARCHIVED METADATA REPO]`

### Execution Workflow

```bash
# For each file:

# 1. Add imports (if needed)
# 2. Wrap each commit location with pattern
# 3. Test incrementally
python run_tests.py tests/db/test_repositories.py -v

# 4. Type check
mypy src/db/repositories/<filename>.py --ignore-missing-imports

# 5. Commit individually or batch
git add src/db/repositories/<filename>.py
git commit -m "feat: add exception handling to <repo_name> commits

Wrapped <N> commits with error handling:
- Line X: <method>()
- Line Y: <method>()

Pattern: OperationalError/Error handlers with rollback.
Part of Phase 2, Task 2.1.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### Final Phase 2.1 Commit

Once all 31 commits wrapped:

```bash
git commit -m "feat: complete phase 2.1 - all repository commits hardened

All 31 commits across 10 repository files now have:
- OperationalError handling (database locked) with rollback
- General Error handling with rollback
- Comprehensive logging with repo-specific prefixes
- Exception chaining for B904 compliance

Complete file list:
- audit_repo.py (1)
- directory_repo.py (3)
- bundle_images_repo.py (4)
- bundle_repo.py (3)
- image_files_repo.py (7)
- metadata_repo.py (4)
- pdf_files_repo.py (3)
- pdf_image_pages_repo.py (3)
- analysis_repo.py (1)
- archived_metadata_repo.py (2)

Phase 2, Task 2.1 COMPLETE ✅

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## 📝 Phase 2 Remaining Tasks (2.2 - 2.5)

### Task 2.2: Config File Writes with Disk Space Check (2 days)

**Files:**
- `src/config/config_manager.py`
- `src/config/appdata_manager.py`

**Implementation:**

Add helper function to both files:

```python
import os

def _check_disk_space(file_path: str, required_bytes: int) -> bool:
    """
    Check if sufficient disk space available.

    Args:
        file_path: Path to check disk space for
        required_bytes: Minimum bytes required

    Returns:
        True if sufficient space (with 2x safety margin)
    """
    try:
        stat = os.statvfs(os.path.dirname(file_path))
        available = stat.f_bavail * stat.f_frsize
        return available > required_bytes * 2  # 2x safety margin
    except Exception:
        return True  # Assume sufficient if check fails
```

**Use before all file writes:**
- `ConfigManager._save_config()`
- `AppdataManager._initialize_settings()`
- `AppdataManager._initialize_database()`
- `AppdataManager._backup_database()`

**Tests to add:**
- `test_save_config_checks_disk_space()`
- `test_save_config_raises_when_disk_full()`

### Task 2.3: Type Conversions (2 days)

**File:** `src/config/config_manager.py`

**Enhance type safety:**

```python
def get_int(self, section: str, key: str, default: int = 0) -> int:
    """Get an integer setting with validation"""
    try:
        value = self.config.get(section, key, fallback=str(default))
        return int(value)
    except ValueError as e:
        logger.warning(
            f"[CONFIG] Invalid integer [{section}] {key}='{value}', "
            f"using default {default}"
        )
        return default

def get_float(self, section: str, key: str, default: float = 0.0) -> float:
    """Get a float setting with validation"""
    try:
        value = self.config.get(section, key, fallback=str(default))
        return float(value)
    except ValueError as e:
        logger.warning(
            f"[CONFIG] Invalid float [{section}] {key}='{value}', "
            f"using default {default}"
        )
        return default
```

**Tests to add** (`tests/config/test_config_manager.py`):
- `test_get_int_handles_invalid_value()`
- `test_get_int_logs_warning_on_invalid()`
- `test_get_float_handles_invalid_value()`
- `test_get_float_logs_warning_on_invalid()`

### Task 2.4: Network Operations in CLI Providers (3 days)

**Files:**
- `src/llm_providers/claude_cli_provider.py`
- `src/llm_providers/gemini_cli_provider.py`

**Pattern for subprocess calls:**

```python
import subprocess

def _run_command(self, cmd: list[str], timeout: int) -> dict[str, Any]:
    """Run CLI command with comprehensive error handling"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )

        if result.returncode != 0:
            logger.error(f"[{self.provider_name}] Command failed: {result.stderr}")
            return {
                "success": False,
                "error": f"Provider failed: {result.stderr}"
            }

        return {"success": True, "output": result.stdout}

    except subprocess.TimeoutExpired:
        logger.error(f"[{self.provider_name}] Timeout after {timeout}s")
        return {
            "success": False,
            "error": f"Provider timed out after {timeout}s. Try increasing timeout."
        }
    except FileNotFoundError:
        logger.error(f"[{self.provider_name}] Command not found: {cmd[0]}")
        return {
            "success": False,
            "error": f"Provider not installed. Install {cmd[0]} and try again."
        }
    except Exception as e:
        logger.error(f"[{self.provider_name}] Unexpected error: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Provider error: {e}"
        }
```

**Apply to both providers** in their `analyze_images()` methods.

**Tests to add** (for BOTH providers):
- `test_analyze_images_handles_timeout()`
- `test_analyze_images_handles_command_not_found()`
- `test_analyze_images_handles_nonzero_exit_code()`
- `test_analyze_images_handles_unexpected_error()`

### Task 2.5: Provider Initialization (2 days)

**Files:**
- `src/llm_providers/ollama_provider.py`
- `src/llm_providers/claude_cli_provider.py`
- `src/llm_providers/gemini_cli_provider.py`

**Pattern for test_connection():**

```python
def test_connection(self) -> bool:
    """
    Test provider connection with error handling.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        result = self._perform_connection_test()
        return result
    except ConnectionError as e:
        logger.warning(f"[{self.provider_name}] Connection test failed: {e}")
        return False
    except Exception as e:
        logger.error(
            f"[{self.provider_name}] Unexpected error during connection test: {e}"
        )
        return False
```

**Apply to all 3 providers.**

**Tests to add:**
- `test_connection_returns_false_on_connection_error()`
- `test_connection_returns_false_on_unexpected_error()`
- `test_connection_logs_errors_appropriately()`

---

## 🎯 Phase 3 Overview (23 tasks - Optional Quality Improvements)

### 3.1 Enhance Existing Error Handling (4 days)

**Goal:** Replace generic `except Exception` with specific types

**Files to audit:**
- All `src/services/*.py` files
- All `src/llm_providers/*.py` files

**Pattern:**
```python
# BEFORE:
try:
    risky_operation()
except Exception as e:  # Too generic
    logger.error(f"Error: {e}")

# AFTER:
try:
    risky_operation()
except FileNotFoundError as e:
    logger.error(f"[SERVICE] File not found: {e}")
    # Handle specifically
except PermissionError as e:
    logger.error(f"[SERVICE] Permission denied: {e}")
    # Handle specifically
except Exception as e:
    logger.error(f"[SERVICE] Unexpected error: {e}", exc_info=True)
    # Only for truly unexpected cases
```

### 3.2 Add Input Validation (3 days)

**Goal:** Validate all public method inputs

**Pattern:**
```python
def process_file(self, file_path: str, batch_size: int = 10) -> dict:
    """Process file with input validation"""
    # Validate string inputs
    if not file_path:
        raise ValueError("file_path cannot be empty")
    if not isinstance(file_path, str):
        raise TypeError(f"file_path must be str, got {type(file_path)}")

    # Validate file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File does not exist: {file_path}")

    # Validate numeric ranges
    if batch_size < 1:
        raise ValueError(f"batch_size must be positive, got {batch_size}")
    if batch_size > 1000:
        raise ValueError(f"batch_size too large (max 1000), got {batch_size}")

    # Proceed with validated inputs
    ...
```

**Apply to all public methods** in service and provider classes.

---

## 🚀 Quick Start Commands

```bash
# Resume work
cd C:\development\scan_organization
git checkout refactor/exception-handling-comprehensive
git status

# Verify what's complete
git log --oneline -20

# Start with easiest file (1 commit)
# File: src/db/repositories/analysis_repo.py
# Line: 248
# Already has all imports, just wrap the commit

# Test after each file
python run_tests.py tests/db/test_repositories.py -v

# Type check
mypy src/db/repositories/ --ignore-missing-imports

# Commit progress
git add src/db/repositories/<filename>.py
git commit -m "feat: add exception handling to <repo> commits (phase 2.1)"
```

---

## 📊 Time Estimates

| Task | Commits/Files | Estimated Time |
|------|--------------|----------------|
| **Phase 2.1 remaining** | 23 commits | 3-4 hours |
| **Phase 2.2** | 2 files | 4-6 hours |
| **Phase 2.3** | 1 file + tests | 4-6 hours |
| **Phase 2.4** | 2 files + tests | 8-12 hours |
| **Phase 2.5** | 3 files + tests | 6-8 hours |
| **Phase 2 Total** | - | **1-2 weeks** |
| **Phase 3** | 23 tasks | **1-2 weeks** |
| **Grand Total** | - | **3-4 weeks** |

---

## ✅ Success Criteria

### Phase 2.1 Complete When:
- [ ] All 31 repository commits wrapped with exception handling
- [ ] All repository tests pass (`python run_tests.py tests/db/`)
- [ ] Type checking clean (`mypy src/db/repositories/`)
- [ ] Final commit message includes all 10 files

### Phase 2 Complete When:
- [ ] Config operations check disk space before writes
- [ ] Type conversions validate and log invalid values
- [ ] CLI providers handle timeout, not found, errors
- [ ] Provider initialization never crashes

### Phase 3 Complete When:
- [ ] No generic `except Exception` without specific handlers first
- [ ] All error messages include actionable guidance
- [ ] All public methods validate inputs

---

## 📞 Support

- **Original Plan:** `C:\Users\erik.OPBTA\.claude\plans\glistening-stirring-panda.md`
- **Project Docs:** `C:\development\scan_organization\CLAUDE.md`
- **Test Runner:** `python run_tests.py tests/ -v`
- **Type Checker:** `mypy src/ --ignore-missing-imports`

**Questions?** Refer to completed Phase 1 tasks (commits `7fb55ef` through `749d252`) for patterns and examples.

---

**Good luck! The foundation is solid—finish strong! 💪**
