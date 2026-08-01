<#
.SYNOPSIS
    Run the local verification gate (the replacement for GitHub Actions CI).

.DESCRIPTION
    Thin wrapper around scripts/verify.py. Runs the full gate by default:
    ruff check + ruff format --check + mypy + bandit + the complete test
    suite + package build/twine check. Use -Quick for the fast pre-push
    subset (ruff + mypy + curated tests, ~30-60s).

.EXAMPLE
    .\scripts\verify.ps1            # full gate — run before opening a PR
    .\scripts\verify.ps1 -Quick     # fast gate — same checks the pre-push hook runs
#>
[CmdletBinding()]
param(
    [switch]$Quick
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

# Prefer the project venv interpreter; fall back to whatever python is on PATH.
$py = Join-Path $repoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$scriptArgs = @((Join-Path $repoRoot "scripts\verify.py"))
if ($Quick) { $scriptArgs += "--quick" }

& $py @scriptArgs
exit $LASTEXITCODE
