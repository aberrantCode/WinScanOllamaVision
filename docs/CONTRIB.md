# Contributing to WinScanLLM

This document provides guidance for developers contributing to the WinScanLLM project.

## Table of Contents

- [Development Setup](#development-setup)
- [Available Scripts](#available-scripts)
- [Project Structure](#project-structure)
- [Testing Procedures](#testing-procedures)
- [Code Quality Standards](#code-quality-standards)
- [Development Workflow](#development-workflow)
- [Security Guidelines](#security-guidelines)

## Development Setup

### Prerequisites

- **Python 3.10+** (tested on 3.11, 3.12, 3.13)
- **Git** for version control
- **GitHub CLI** (optional but recommended)
- **Virtual environment** support

### Initial Setup

1. **Clone the repository**
   ```powershell
   git clone https://github.com/aberrantCode/WinScanLLM.git
   cd scan_organization
   ```

2. **Create and activate virtual environment**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1  # PowerShell
   # Or for cmd.exe: .\venv\Scripts\activate.bat
   ```

3. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Install pre-commit hooks**
   ```powershell
   pre-commit install
   pre-commit install --hook-type commit-msg
   ```

5. **Verify tooling**
   ```powershell
   .\scripts\verify-tooling.ps1
   ```

### Verifying Your Environment

Run the verification script to ensure all tools are properly configured:

```powershell
.\scripts\verify-tooling.ps1
```

This checks:
- ✓ Python installation and version
- ✓ Virtual environment exists and is activated
- ✓ pytest testing framework
- ✓ GitHub CLI authentication (optional)
- ✓ Git installation and remote configuration

## Available Scripts

### Testing

**Primary test runner (recommended):**
```powershell
python run_tests.py              # Run all tests with coverage
python run_tests.py tests/       # Run all tests
python run_tests.py tests/config # Run specific directory
python run_tests.py -k provider  # Run tests matching pattern
python run_tests.py tests/ -v    # Verbose output
```

**Core tests only (excludes GUI/integration):**
```powershell
python run_tests.py tests/ --ignore=tests/gui --ignore=tests/integration --ignore=tests/services --ignore=tests/prompt
```

**Using pytest directly:**
```powershell
pytest tests/                    # Run all tests
pytest tests/config/             # Run specific module
pytest -k "metadata"             # Run tests matching pattern
pytest --cov-report=html         # Generate HTML coverage report
```

### Code Quality

**Linting and formatting:**
```powershell
ruff check src/                  # Lint source code
ruff format src/                 # Format source code
ruff check --fix src/            # Auto-fix linting issues
```

**Type checking:**
```powershell
mypy src/                        # Check all source files
mypy src/ui/file_details_grid.py --ignore-missing-imports  # Specific file
mypy src/ui/ --ignore-missing-imports                       # Specific module
```

**Security checks:**
```powershell
.\scripts\security-check.ps1     # Run security checks
bandit -r src/                   # Python security linter
pip-audit                        # Check dependencies for vulnerabilities
```

**Pre-commit hooks (manual run):**
```powershell
pre-commit run --all-files       # Run all hooks on all files
```

### Application

**Run the application:**
```powershell
python src/main.py
```

## Project Structure

```
src/
├── main.py              # Application entry point (ONLY file in root)
├── config/              # Configuration management
│   ├── config_manager.py
│   └── appdata_manager.py
├── db/                  # Database layer
│   ├── analysis_db.py   # Analysis results facade
│   ├── metadata_db.py   # Document metadata facade
│   ├── connection.py    # Database connection management
│   ├── schema.py        # Schema migrations
│   └── repositories/    # Repository pattern implementations
│       ├── analysis_repo.py
│       ├── metadata_repo.py
│       ├── image_files_repo.py
│       └── archived_metadata_repo.py
├── services/            # Business logic and orchestration
│   ├── analysis_service.py
│   ├── file_service.py
│   ├── bundling_service.py
│   ├── logging_service.py
│   ├── analysis_queue.py
│   └── metadata_normalizer.py
├── ui/                  # User interface components
│   ├── gui.py
│   ├── analysis_status_window.py
│   ├── bundle_widgets.py
│   ├── bundle_workflow_handlers.py
│   ├── file_details_grid.py
│   ├── settings_window_enhanced.py
│   └── style.py
└── llm_providers/       # LLM provider implementations
    ├── base_provider.py
    ├── provider_factory.py
    ├── ollama_provider.py
    ├── claude_cli_provider.py
    └── gemini_cli_provider.py

tests/
├── config/              # ConfigManager tests
├── db/                  # Database layer tests
├── gui/                 # UI component tests
├── llm_providers/       # Provider implementation tests
├── services/            # Service layer tests
├── integration/         # End-to-end integration tests
└── prompt/              # Prompt optimization tests
```

### Import Rules

- **All imports MUST use full package paths:**
  ```python
  # CORRECT
  from config.config_manager import ConfigManager
  from ui.gui import StartupWindow

  # INCORRECT - no relative imports outside package boundaries
  from ..config import ConfigManager
  ```

- **No root-level imports** - All source code belongs in `src/` packages

### File Placement Rules

- **Tests** → `/tests` (with subfolder structure mirroring `/src`)
- **Source code** → `/src` (with package structure)
- **Scripts & utilities** → `/scripts`
- **Markdown documentation** → `/docs`
- **Images & assets** → `/assets`
- **Databases & import datasets** → `/data` (templates only, actual DBs in AppData)

## Testing Procedures

### Test Framework

This project uses **pytest** (not unittest) for all tests.

### Coverage Requirements

- **Minimum coverage: 90%** (currently at 89%)
- UI code is excluded from coverage but business logic in UI components needs tests
- Tests must cover both success and failure paths

### Writing Tests

1. **Follow existing patterns** - See `tests/llm_providers/test_claude_cli_provider.py`
2. **Mock external dependencies** - Never call real CLI tools or APIs
3. **Test both success and failure** - Including malformed responses
4. **Use descriptive test names** - `test_save_metadata_calls_database`
5. **Arrange-Act-Assert pattern**

Example test structure:
```python
def test_save_metadata_calls_database(mocker):
    """Test that save metadata calls the correct database methods."""
    # Arrange
    mock_analysis_db = mocker.Mock()
    mock_analysis_db.get_analysis_with_metadata.return_value = {...}

    dialog = FileDetailsDialog(
        file_data={"full_path": "/test.png"},
        analysis_db=mock_analysis_db
    )

    # Act
    dialog._save_metadata()

    # Assert
    mock_analysis_db.get_analysis_with_metadata.assert_called_once()
```

### Running Tests

**Before committing (MANDATORY):**

1. **Type check modified files:**
   ```powershell
   mypy src/path/to/modified_file.py --ignore-missing-imports
   ```

2. **Run relevant tests:**
   ```powershell
   python run_tests.py tests/path/to/relevant_tests.py -v
   ```

3. **Verify no regressions:**
   ```powershell
   python run_tests.py tests/ -v
   ```

### Current Test Coverage

| Module | Coverage | Status |
|--------|----------|--------|
| `src/config/` | 95%+ | ✓ Complete |
| `src/db/` | 98%+ | ✓ Complete |
| `src/llm_providers/` | 98%+ | ✓ Complete |
| `src/services/` | 85%+ | ⚠ Improving |
| `src/ui/` | Excluded | ⚠ Business logic needs unit tests |

## Code Quality Standards

### Linting and Formatting (ruff)

Configuration in `pyproject.toml`:
- Target: Python 3.10+
- Line length: 100 characters
- Auto-formatting with double quotes, 4-space indents
- Enabled rules: pycodestyle, Pyflakes, isort, pep8-naming, pyupgrade, flake8-bugbear

### Type Checking (mypy)

Configuration in `pyproject.toml`:
- Python version: 3.10
- Strict typing gradually enabled
- Missing imports ignored for third-party libraries
- Tests excluded from strict checking

### Security Scanning (bandit)

Configuration in `pyproject.toml`:
- Excludes: tests, venv directories
- Skips: B101 (assert_used - acceptable in tests)

### Pre-Commit Hooks

Automatically run on commit:
1. ruff (linting)
2. ruff-format (formatting)
3. mypy (type checking)
4. bandit (security)
5. YAML/JSON/TOML validation
6. Large file detection (>1MB)
7. Merge conflict detection
8. Private key detection
9. Trailing whitespace trimming
10. Conventional commit message validation

## Development Workflow

### Test-Driven Development (TDD)

**MANDATORY workflow:**

1. **Write test first (RED)**
   ```python
   def test_new_feature():
       result = new_feature()
       assert result == expected_value
   ```

2. **Run test - it should FAIL**
   ```powershell
   python run_tests.py tests/test_module.py -k test_new_feature
   ```

3. **Write minimal implementation (GREEN)**

4. **Run test - it should PASS**

5. **Refactor (IMPROVE)**

6. **Verify coverage ≥80%**

### Quality Checklist Before Committing

**MANDATORY checks:**

- [ ] Type check modified files (`mypy src/path/to/file.py`)
- [ ] Run relevant tests (`python run_tests.py tests/path/`)
- [ ] Lint code (`ruff check src/`)
- [ ] Format code (`ruff format src/`)
- [ ] All tests pass locally
- [ ] No hardcoded secrets or sensitive data
- [ ] No `console.log` or debug print statements
- [ ] Documentation updated if needed

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>

[optional body]

[optional footer]
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code refactoring
- `docs:` - Documentation changes
- `test:` - Test additions/changes
- `chore:` - Maintenance tasks
- `perf:` - Performance improvements
- `ci:` - CI/CD changes

**Example:**
```
feat: add metadata normalization service

Implement MetadataNormalizer to automatically normalize document
metadata fields (company, document_type, date) from LLM responses.

Includes validation, type coercion, and error handling.
```

### Pull Request Workflow

1. **Create feature branch**
   ```powershell
   git checkout -b feature/your-feature-name
   ```

2. **Make changes following TDD**

3. **Run full test suite**
   ```powershell
   python run_tests.py tests/ -v
   ```

4. **Commit changes**
   ```powershell
   git add .
   git commit -m "feat: your feature description"
   ```

5. **Push to remote**
   ```powershell
   git push -u origin feature/your-feature-name
   ```

6. **Create pull request** (via GitHub UI or `gh` CLI)
   ```powershell
   gh pr create --title "Feature: Your Feature" --body "Description..."
   ```

## Security Guidelines

### Mandatory Security Checks

**Before ANY commit:**

- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs validated
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (sanitized HTML)
- [ ] Authentication/authorization verified
- [ ] Error messages don't leak sensitive data

### Secret Management

```python
# NEVER: Hardcoded secrets
api_key = "sk-proj-xxxxx"

# ALWAYS: Environment variables
api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("API_KEY not configured")
```

### Running Security Checks

```powershell
# Pre-commit security check (recommended before every commit)
.\scripts\security-check.ps1

# Manual security scanning
bandit -r src/                   # Python security linter
pip-audit                        # Dependency vulnerability scan
```

The security check script verifies:
- ✓ No `.env` files staged for commit
- ✓ No hardcoded secrets in staged changes
- ✓ No sensitive files (`.pem`, `.key`, `credentials.json`)
- ✓ No known vulnerabilities in dependencies

### Common Security Pitfalls

1. **Don't hardcode credentials** - Use environment variables or config files (excluded from git)
2. **Don't commit `.env` files** - Only commit `.env.example` templates
3. **Don't log sensitive data** - Sanitize logs before writing
4. **Don't trust user input** - Always validate and sanitize
5. **Don't expose stack traces** - Use generic error messages for users

## Additional Resources

- [Python Style Guide](https://pep8.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [ruff Documentation](https://docs.astral.sh/ruff/)
- [pre-commit Documentation](https://pre-commit.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/aberrantCode/WinScanLLM/issues)
- **Discussions:** [GitHub Discussions](https://github.com/aberrantCode/WinScanLLM/discussions)
- **Documentation:** See `/docs` directory

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.
