# GitHub Actions Workflows

This directory contains automated CI/CD workflows for the WinScanOllamaVision project.

## Workflows

### 1. CI (ci.yml)

**Triggers:** Push to main branches, pull requests

**Jobs:**
- **test** - Runs test suite on multiple Python versions (3.11, 3.12, 3.13) and OS (Ubuntu, Windows)
  - Installs system dependencies (Qt libraries on Linux)
  - Runs pytest with coverage
  - Uploads coverage to Codecov
  - Generates JUnit XML reports
  - Uses xvfb on Linux for GUI tests
  - Parallel test execution with pytest-xdist

- **lint** - Code quality checks
  - Ruff linting and formatting
  - Mypy type checking
  - Bandit security scanning
  - Uploads security reports

- **coverage-report** - Generates and publishes coverage reports
  - HTML coverage report
  - PR coverage comments
  - Coverage badges

- **build-check** - Validates package building
  - Builds wheel and sdist
  - Runs twine check
  - Uploads build artifacts

**Requirements:**
- Tests must pass with 90%+ coverage
- All linting checks must pass
- No security issues from Bandit

### 2. CodeQL Security Scan (codeql.yml)

**Triggers:** Push to master, pull requests, weekly schedule (Monday 6 AM UTC)

**Features:**
- Automated security vulnerability detection
- Extended security queries
- Code quality analysis
- GitHub Security tab integration

### 3. PR Checks (pr-checks.yml)

**Triggers:** Pull request events (opened, synchronized, reopened, edited)

**Checks:**
- **PR title validation** - Ensures conventional commit format
- **Breaking changes detection** - Flags PRs with breaking changes
- **PR size labeling** - Auto-labels by lines changed (xs/s/m/l/xl)
- **File-based labeling** - Auto-labels by changed files
- **Test status** - Required status check for merging
- **Coverage requirement** - Ensures 90% coverage

### 4. Release (release.yml)

**Triggers:** Git tags matching `v*.*.*` (e.g., v1.0.0)

**Jobs:**
- **create-release** - Creates GitHub release
  - Generates changelog from commits
  - Builds Python package
  - Creates release notes
  - Publishes to PyPI (stable releases only)

- **build-executables** - Builds platform-specific executables
  - Windows .exe
  - Linux binary
  - macOS .app
  - Attaches to GitHub release

**Tag format:**
- `v1.0.0` - Stable release (publishes to PyPI)
- `v1.0.0-alpha.1` - Alpha release (GitHub only)
- `v1.0.0-beta.1` - Beta release (GitHub only)
- `v1.0.0-rc.1` - Release candidate (GitHub only)

## Configuration Files

### dependabot.yml

Automated dependency updates:
- **Python packages** - Weekly updates on Monday
- **GitHub Actions** - Weekly updates on Monday
- Groups related updates (pytest, PyQt6, dev dependencies)
- Auto-assigns to project maintainer

### labeler.yml

Automatic PR labeling based on files changed:
- **Area labels** - ui, database, services, config, providers, tests, ci, docs
- **Type labels** - documentation, dependencies, tests
- **Priority labels** - high (for hotfix/critical branches)
- **Status labels** - needs-review (for source code changes)

## Setup Requirements

### GitHub Secrets

Required secrets for workflows:

1. **CODECOV_TOKEN** (optional)
   - For Codecov integration
   - Get from: https://codecov.io

2. **PYPI_TOKEN** (required for releases)
   - For publishing to PyPI
   - Get from: https://pypi.org/manage/account/token/

### Branch Protection Rules

Recommended settings for `master` branch:

- ✅ Require pull request before merging
- ✅ Require approvals: 1
- ✅ Require status checks to pass:
  - `test` (CI workflow)
  - `lint` (CI workflow)
  - `Test Status Check` (PR checks)
  - `Coverage Requirement` (PR checks)
- ✅ Require conversation resolution before merging
- ✅ Require signed commits
- ✅ Include administrators

## Running Workflows Locally

### Test workflow (act)

Install [act](https://github.com/nektos/act):
```bash
# macOS
brew install act

# Windows
choco install act-cli

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

Run workflow locally:
```bash
# Run CI workflow
act -j test

# Run lint job
act -j lint

# List all jobs
act -l
```

### Pre-commit hooks

Install pre-commit locally to catch issues before pushing:
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Monitoring and Debugging

### View workflow runs

https://github.com/aberrantCode/WinScanOllamaVision/actions

### Download artifacts

Artifacts are available for 90 days:
- Test results (JUnit XML)
- Coverage reports (HTML)
- Security reports (Bandit JSON)
- Build artifacts (wheels, executables)

### Debug failing workflows

1. Check the workflow run logs
2. Look for failed steps with ❌
3. Expand step details for error messages
4. Check artifact uploads for detailed reports

### Common issues

**Qt dependencies on Linux:**
- Ensure xvfb is running for GUI tests
- Install all required Qt libraries

**Coverage failures:**
- Check coverage report artifact
- Ensure test coverage is >= 90%
- GUI tests may need special handling

**Timeout issues:**
- Default timeout is 300 seconds per test
- Adjust `--timeout=N` in pytest command
- Check for hanging tests

## Badges

Add these badges to your README.md:

```markdown
[![CI](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/ci.yml/badge.svg)](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/aberrantCode/WinScanOllamaVision/branch/master/graph/badge.svg)](https://codecov.io/gh/aberrantCode/WinScanOllamaVision)
[![CodeQL](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/codeql.yml/badge.svg)](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/codeql.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
```

## Maintenance

### Updating workflows

1. Edit workflow files in `.github/workflows/`
2. Test locally with `act` if possible
3. Create PR with changes
4. Workflows will run on the PR
5. Merge after validation

### Updating dependencies

1. Dependabot creates PRs automatically
2. Review changes in the PR
3. Ensure tests pass
4. Merge if all checks pass

### Security updates

1. Check GitHub Security tab regularly
2. Review Dependabot security PRs
3. Address CodeQL findings
4. Update pinned action versions

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [Codecov Documentation](https://docs.codecov.com/)
- [CodeQL Documentation](https://codeql.github.com/docs/)
