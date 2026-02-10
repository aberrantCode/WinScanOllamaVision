# Scripts Reference

Quick reference for all available scripts and commands in the WinScanLLM project.

## Table of Contents

- [Test Scripts](#test-scripts)
- [Development Scripts](#development-scripts)
- [Code Quality Scripts](#code-quality-scripts)
- [Security Scripts](#security-scripts)
- [Database Scripts](#database-scripts)
- [pyproject.toml Scripts](#pyprojecttoml-scripts)

## Test Scripts

### run_tests.py

**Primary test runner** - Ensures `src/` is in Python path before running pytest.

**Location:** `./run_tests.py`

**Usage:**
```powershell
python run_tests.py                    # Run all tests with coverage
python run_tests.py tests/             # Run all tests
python run_tests.py tests/config       # Run specific directory
python run_tests.py tests/config/test_config_manager.py  # Run specific file
python run_tests.py -k provider        # Run tests matching pattern
python run_tests.py tests/ -v          # Verbose output
python run_tests.py tests/ --tb=short  # Short traceback format
```

**Default behavior:**
- Adds `src/` to Python path automatically
- Runs with coverage reporting
- Generates HTML coverage report in `htmlcov/`
- Fails if coverage < 90%

**Coverage exclusions:**
- `*/ollama_service.py` (thin SDK wrapper)
- `*/main.py` (application entry point)
- `*/ui/*` (GUI components - tested separately)

### pytest (direct)

**Test framework** - Can be used directly if you don't need custom path setup.

**Usage:**
```powershell
pytest tests/                          # Run all tests
pytest tests/config/                   # Run specific module
pytest -k "metadata"                   # Run tests matching pattern
pytest --cov-report=html               # Generate HTML coverage report
pytest --cov-report=term-missing       # Show missing lines in terminal
pytest -v                              # Verbose output
pytest -x                              # Stop on first failure
pytest --tb=short                      # Short traceback format
pytest --collect-only                  # List tests without running
```

**Configuration:** `pyproject.toml` section `[tool.pytest.ini_options]`

## Development Scripts

### verify-tooling.ps1

**Development environment verification** - Checks all required tools are installed and configured.

**Location:** `./scripts/verify-tooling.ps1`

**Usage:**
```powershell
.\scripts\verify-tooling.ps1
```

**Checks:**
- ✓ Python installation and version
- ✓ Virtual environment exists at `.\venv\`
- ✓ Virtual environment is activated
- ✓ pytest installed
- ✓ GitHub CLI authenticated (optional)
- ✓ Git installed and remote configured

**Exit codes:**
- `0` - All checks passed
- `1` - Some tools missing or misconfigured

### setup-dev-environment.ps1

**Development environment setup** - Automates initial project setup (if exists).

**Location:** `./scripts/setup-dev-environment.ps1`

**Usage:**
```powershell
.\scripts\setup-dev-environment.ps1
```

**Actions:**
- Creates virtual environment
- Installs dependencies from `requirements.txt`
- Installs pre-commit hooks
- Runs tooling verification

## Code Quality Scripts

### ruff (linter)

**Python linter and code formatter** - Fast Python linter written in Rust.

**Configuration:** `pyproject.toml` section `[tool.ruff]`

**Linting:**
```powershell
ruff check src/                        # Lint source code
ruff check tests/                      # Lint tests
ruff check src/ --fix                  # Auto-fix issues
ruff check src/ --watch                # Watch mode (re-lint on changes)
ruff check src/ --output-format=json   # JSON output for CI
```

**Formatting:**
```powershell
ruff format src/                       # Format source code
ruff format tests/                     # Format tests
ruff format --check src/               # Check without modifying
ruff format --diff src/                # Show diff without modifying
```

**Rules enabled:**
- E, W - pycodestyle (PEP 8)
- F - Pyflakes (unused imports, undefined names)
- I - isort (import sorting)
- N - pep8-naming (naming conventions)
- UP - pyupgrade (Python version upgrades)
- B - flake8-bugbear (common bugs)
- C4 - flake8-comprehensions (list/dict comprehensions)
- SIM - flake8-simplify (code simplification)

**Configuration highlights:**
- Line length: 100 characters
- Target: Python 3.10+
- Double quotes for strings
- 4-space indentation

### mypy (type checker)

**Static type checker** - Validates type annotations.

**Configuration:** `pyproject.toml` section `[tool.mypy]`

**Usage:**
```powershell
mypy src/                              # Check all source files
mypy src/ui/file_details_grid.py --ignore-missing-imports  # Specific file
mypy src/ui/ --ignore-missing-imports  # Specific module
mypy src/ --strict                     # Strict type checking
mypy src/ --show-error-codes           # Show error codes
mypy src/ --install-types              # Install missing type stubs
```

**Configuration highlights:**
- Target: Python 3.10
- `ignore_missing_imports = true` (third-party libraries)
- `disallow_untyped_defs = false` (gradually enabling)
- Tests excluded from checking

**Common flags:**
- `--ignore-missing-imports` - Ignore third-party library type issues
- `--strict` - Enable all strict checks
- `--show-error-codes` - Show error codes for suppression

### pre-commit

**Git hook manager** - Runs code quality checks before commits.

**Configuration:** `.pre-commit-config.yaml`

**Usage:**
```powershell
pre-commit install                     # Install git hooks
pre-commit install --hook-type commit-msg  # Install commit-msg hook
pre-commit run --all-files             # Run all hooks on all files
pre-commit run ruff                    # Run specific hook
pre-commit run --files src/file.py     # Run on specific file
pre-commit autoupdate                  # Update hook versions
```

**Hooks enabled:**
1. ruff (linting)
2. ruff-format (formatting)
3. mypy (type checking)
4. bandit (security)
5. check-yaml, check-json, check-toml (file validation)
6. check-added-large-files (prevent large files, >1MB)
7. check-merge-conflict (detect merge conflicts)
8. detect-private-key (prevent committing keys)
9. trailing-whitespace (trim whitespace)
10. end-of-file-fixer (ensure newline at EOF)
11. conventional-commit (validate commit messages)

**Skip hooks temporarily:**
```powershell
git commit --no-verify                 # Skip all hooks (use sparingly)
SKIP=mypy git commit                   # Skip specific hook
```

## Security Scripts

### security-check.ps1

**Security validation** - Checks for security issues before committing.

**Location:** `./scripts/security-check.ps1`

**Usage:**
```powershell
.\scripts\security-check.ps1
```

**Checks:**
- ✓ No `.env` files staged for commit
- ✓ No hardcoded secrets in staged changes (patterns: password, secret, api_key, token)
- ✓ No sensitive files staged (`.pem`, `.key`, `.p12`, `credentials.json`, `secrets.json`)
- ✓ No known vulnerabilities in dependencies (via `pip-audit`)

**Exit codes:**
- `0` - All checks passed
- `1` - Security issues found

**Secret patterns detected:**
```regex
password\s*[:=]\s*["'][^"']{8,}["']
secret\s*[:=]\s*["'][^"']{8,}["']
api_key\s*[:=]\s*["'][^"']{8,}["']
apikey\s*[:=]\s*["'][^"']{8,}["']
token\s*[:=]\s*["'][^"']{20,}["']
```

### bandit

**Python security linter** - Finds common security issues in Python code.

**Configuration:** `pyproject.toml` section `[tool.bandit]`

**Usage:**
```powershell
bandit -r src/                         # Scan source code
bandit -r src/ -f json                 # JSON output for CI
bandit -r src/ -ll                     # Low confidence, low severity
bandit -r src/ -s B101                 # Skip specific test
bandit -r src/ --baseline bandit.json  # Compare to baseline
```

**Configuration highlights:**
- Excludes: `tests/`, `venv/`, `.venv/`
- Skips: B101 (assert_used - acceptable in tests)

**Common issues detected:**
- Hardcoded passwords
- SQL injection vulnerabilities
- Shell injection vulnerabilities
- Weak cryptography
- Insecure deserialization

### pip-audit

**Dependency vulnerability scanner** - Checks for known vulnerabilities in dependencies.

**Usage:**
```powershell
pip-audit                              # Scan all dependencies
pip-audit --fix                        # Auto-upgrade vulnerable packages
pip-audit --format json                # JSON output for CI
pip-audit --ignore-vuln PYSEC-2023-123 # Ignore specific vulnerability
pip-audit --dry-run --fix              # Show what would be upgraded
```

**Exit codes:**
- `0` - No vulnerabilities found
- `1` - Vulnerabilities found

## Database Scripts

### SQLite Management

**Database maintenance** - Direct SQLite commands for database management.

**Check integrity:**
```powershell
sqlite3 "$env:APPDATA\WinScanLLM\analysis.db" "PRAGMA integrity_check;"
sqlite3 "$env:APPDATA\WinScanLLM\metadata.db" "PRAGMA integrity_check;"
```

**Vacuum (reclaim space):**
```powershell
sqlite3 "$env:APPDATA\WinScanLLM\analysis.db" "VACUUM;"
sqlite3 "$env:APPDATA\WinScanLLM\metadata.db" "VACUUM;"
```

**Analyze (optimize queries):**
```powershell
sqlite3 "$env:APPDATA\WinScanLLM\analysis.db" "ANALYZE;"
sqlite3 "$env:APPDATA\WinScanLLM\metadata.db" "ANALYZE;"
```

**Check schema version:**
```powershell
sqlite3 "$env:APPDATA\WinScanLLM\analysis.db" "SELECT * FROM schema_version ORDER BY version DESC LIMIT 1;"
sqlite3 "$env:APPDATA\WinScanLLM\metadata.db" "SELECT * FROM schema_version ORDER BY version DESC LIMIT 1;"
```

**Backup databases:**
```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item "$env:APPDATA\WinScanLLM\analysis.db" "$env:APPDATA\WinScanLLM\backup\analysis_$timestamp.db"
Copy-Item "$env:APPDATA\WinScanLLM\metadata.db" "$env:APPDATA\WinScanLLM\backup\metadata_$timestamp.db"
```

## pyproject.toml Scripts

### Build Scripts

**Build distribution packages:**

```powershell
# Install build dependencies
pip install build wheel

# Create distribution packages
python -m build

# Output files:
# dist/winscan_llm-0.1.0.tar.gz
# dist/winscan_llm-0.1.0-py3-none-any.whl
```

### Tool Configuration

All tool configurations are centralized in `pyproject.toml`:

**[tool.ruff]**
- Line length: 100
- Target version: Python 3.10+
- Excludes: `.git`, `.venv`, `venv`, `__pycache__`, `build`, `dist`, `.pytest_cache`

**[tool.ruff.lint]**
- Rules: E, W, F, I, N, UP, B, C4, SIM
- Ignores: E501 (line too long - handled by formatter)

**[tool.ruff.format]**
- Quote style: double
- Indent style: space (4 spaces)

**[tool.mypy]**
- Python version: 3.10
- `warn_return_any = true`
- `warn_unused_configs = true`
- `disallow_untyped_defs = false` (gradually enabling)
- `ignore_missing_imports = true`
- Excludes: `venv`, `.venv`, `tests`

**[tool.bandit]**
- Excludes: `tests`, `venv`, `.venv`
- Skips: B101 (assert_used)

**[tool.pytest.ini_options]**
- Test paths: `tests/`
- Coverage: `--cov=src` with `--cov-fail-under=90`
- Coverage report: terminal (missing lines) + HTML
- Verbose: `-v`
- Omit from coverage: `*/ollama_service.py`, `*/main.py`, `*/ui/*`

## Quick Reference

### Common Workflows

**Before committing:**
```powershell
# Type check
mypy src/path/to/modified_file.py --ignore-missing-imports

# Run tests
python run_tests.py tests/path/to/relevant_tests.py -v

# Lint and format
ruff check src/ --fix
ruff format src/

# Security check
.\scripts\security-check.ps1

# Run pre-commit hooks
pre-commit run --all-files
```

**Running full validation:**
```powershell
# Run all tests with coverage
python run_tests.py tests/ -v

# Type check all files
mypy src/ --ignore-missing-imports

# Security scan
bandit -r src/
pip-audit

# Pre-commit checks
pre-commit run --all-files
```

**Setting up new development environment:**
```powershell
# Clone repository
git clone https://github.com/aberrantCode/WinScanLLM.git
cd scan_organization

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Verify environment
.\scripts\verify-tooling.ps1

# Run tests
python run_tests.py tests/ -v
```

## Environment Variables

**Note:** This project uses `settings.ini` configuration instead of environment variables.

**AppData location:**
- Configuration: `%APPDATA%\WinScanLLM\settings.ini`
- Databases: `%APPDATA%\WinScanLLM\*.db`
- Logs: `%APPDATA%\WinScanLLM\logs\app.log`

**No `.env` file required.**

## CI/CD Integration

### GitHub Actions (example)

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python run_tests.py tests/ -v
      - name: Type check
        run: mypy src/ --ignore-missing-imports
      - name: Lint
        run: ruff check src/
      - name: Security scan
        run: bandit -r src/
```

## Troubleshooting

### Tests fail with import errors

**Solution:** Use `python run_tests.py` instead of `pytest` directly.

```powershell
# WRONG: Direct pytest may not find src/
pytest tests/

# CORRECT: run_tests.py adds src/ to path
python run_tests.py tests/
```

### Pre-commit hook fails

**Solution:** Fix the issue or skip temporarily (use sparingly).

```powershell
# Fix the issue
ruff check src/ --fix

# Or skip temporarily (NOT recommended)
git commit --no-verify
```

### mypy errors about missing imports

**Solution:** Use `--ignore-missing-imports` flag.

```powershell
mypy src/path/to/file.py --ignore-missing-imports
```

### Coverage below 90%

**Solution:** Add tests for uncovered code or adjust coverage threshold.

```powershell
# View coverage report
python run_tests.py tests/ -v

# Generate HTML report for details
pytest tests/ --cov-report=html
# Open htmlcov/index.html in browser
```

## Additional Resources

- **pytest docs:** https://docs.pytest.org/
- **ruff docs:** https://docs.astral.sh/ruff/
- **mypy docs:** https://mypy.readthedocs.io/
- **bandit docs:** https://bandit.readthedocs.io/
- **pre-commit docs:** https://pre-commit.com/
