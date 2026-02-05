<!--
LOG DECISIONS WHEN:
- Choosing between architectural approaches
- Selecting libraries or tools
- Making security-related choices
- Deviating from standard patterns

This is append-only. Never delete entries.
-->

# Decision Log

Track key architectural and implementation decisions.

## Format

```
## [YYYY-MM-DD] Decision Title

**Decision**: What was decided
**Context**: Why this decision was needed
**Options Considered**: What alternatives existed
**Choice**: Which option was chosen
**Reasoning**: Why this choice was made
**Trade-offs**: What we gave up
**References**: Related code/docs
```

---

## [2026-02-04] Use PowerShell for Windows-specific scripts

**Decision**: Create verification and security scripts as `.ps1` (PowerShell) instead of `.sh` (bash)

**Context**: This is a Windows-focused application using AppData directories, PyQt6 GUI, and PowerShell activation scripts for venv

**Options Considered**:
1. Bash scripts (cross-platform but requires Git Bash/WSL on Windows)
2. PowerShell scripts (Windows-native)
3. Python scripts (cross-platform)

**Choice**: PowerShell scripts

**Reasoning**:
- Windows is the primary/only target platform
- Existing CLAUDE.md uses PowerShell examples
- Venv activation already uses `.\venv\Scripts\Activate.ps1`
- Native Windows experience without external dependencies

**Trade-offs**:
- Not cross-platform (but not a requirement)
- Requires PowerShell execution policy configured

**References**: `scripts/verify-tooling.ps1`, `scripts/security-check.ps1`

---

## [2026-02-04] Keep unittest framework instead of migrating to pytest

**Decision**: Continue using unittest framework despite pytest being installed

**Context**: The codebase uses `unittest.TestCase` throughout tests, and CLAUDE.md explicitly documents unittest patterns

**Options Considered**:
1. Migrate all tests to pytest
2. Keep unittest, use pytest only as test runner
3. Keep unittest completely

**Choice**: Keep unittest framework (option 3)

**Reasoning**:
- Existing tests all use unittest patterns
- CLAUDE.md specifically documents unittest usage
- No compelling reason to migrate (both frameworks are mature)
- Avoid breaking existing test infrastructure

**Trade-offs**:
- Miss some pytest features (fixtures, parametrize)
- Pytest is installed but only for coverage tracking (pytest-cov)

**References**: `tests/` directory, `CLAUDE.md` testing section

---
