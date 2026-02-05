# verify-tooling.ps1
# Verify project tooling is installed and configured

$ErrorActionPreference = "Continue"
Write-Host "Verifying project tooling..." -ForegroundColor Cyan
Write-Host ""

$allOk = $true

# Python
Write-Host "Python:" -ForegroundColor Yellow
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonVersion = python --version
    Write-Host "  ✓ Python installed: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ Python not found in PATH" -ForegroundColor Red
    $allOk = $false
}

# Virtual environment
Write-Host "`nVirtual Environment:" -ForegroundColor Yellow
if (Test-Path "venv\Scripts\activate.ps1") {
    Write-Host "  ✓ Virtual environment exists at .\venv\" -ForegroundColor Green
    if ($env:VIRTUAL_ENV) {
        Write-Host "  ✓ Virtual environment is activated" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ Virtual environment not activated. Run: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✗ Virtual environment not found. Run: python -m venv venv" -ForegroundColor Red
    $allOk = $false
}

# Pytest
Write-Host "`nTesting Framework:" -ForegroundColor Yellow
if (Get-Command pytest -ErrorAction SilentlyContinue) {
    $pytestVersion = pytest --version 2>&1 | Select-Object -First 1
    Write-Host "  ✓ pytest installed: $pytestVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ pytest not installed. Run: pip install -r requirements.txt" -ForegroundColor Red
    $allOk = $false
}

# GitHub CLI
Write-Host "`nGitHub CLI:" -ForegroundColor Yellow
if (Get-Command gh -ErrorAction SilentlyContinue) {
    $ghStatus = gh auth status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ GitHub CLI authenticated" -ForegroundColor Green
    } else {
        Write-Host "  ✗ GitHub CLI not authenticated. Run: gh auth login" -ForegroundColor Red
    }
} else {
    Write-Host "  ⚠ GitHub CLI not installed (optional)" -ForegroundColor Yellow
}

# Git
Write-Host "`nGit:" -ForegroundColor Yellow
if (Get-Command git -ErrorAction SilentlyContinue) {
    $gitVersion = git --version
    Write-Host "  ✓ Git installed: $gitVersion" -ForegroundColor Green

    $remote = git remote get-url origin 2>$null
    if ($remote) {
        Write-Host "  ✓ Git remote configured: $remote" -ForegroundColor Green
    } else {
        Write-Host "  ⚠ No git remote configured" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✗ Git not found" -ForegroundColor Red
    $allOk = $false
}

Write-Host ""
if ($allOk) {
    Write-Host "Tooling verification complete! ✓" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some tools are missing or misconfigured." -ForegroundColor Red
    exit 1
}
