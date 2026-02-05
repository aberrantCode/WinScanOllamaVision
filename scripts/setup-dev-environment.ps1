# setup-dev-environment.ps1
# Complete development environment setup script

$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  WinScanLLM Dev Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv\Scripts\activate.ps1")) {
    Write-Host "Virtual environment not found!" -ForegroundColor Red
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
    Write-Host ""
}

# Check if we're in a virtual environment
if (-not $env:VIRTUAL_ENV) {
    Write-Host "⚠ Virtual environment not activated" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "IMPORTANT: You need to activate the virtual environment first!" -ForegroundColor Yellow
    Write-Host "Run this command, then run this script again:" -ForegroundColor Cyan
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "✓ Virtual environment is activated" -ForegroundColor Green
Write-Host ""

Write-Host "Step 1: Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip --quiet
Write-Host "✓ pip upgraded" -ForegroundColor Green
Write-Host ""

Write-Host "Step 2: Installing dependencies from requirements.txt..." -ForegroundColor Cyan
Write-Host "  (This may take a few minutes)" -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ All dependencies installed" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "Step 3: Installing pre-commit hooks..." -ForegroundColor Cyan
pre-commit install --install-hooks 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Pre-commit hooks installed" -ForegroundColor Green
} else {
    Write-Host "⚠ Failed to install pre-commit hooks" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "Step 4: Installing commit-msg hook..." -ForegroundColor Cyan
pre-commit install --hook-type commit-msg 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Commit-msg hook installed" -ForegroundColor Green
} else {
    Write-Host "⚠ Failed to install commit-msg hook" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "Step 5: Verifying installation..." -ForegroundColor Cyan
Write-Host ""

$allGood = $true

# Check ruff
Write-Host "  Checking ruff..." -NoNewline
if (Get-Command ruff -ErrorAction SilentlyContinue) {
    $ruffVersion = ruff --version 2>&1
    Write-Host " ✓ $ruffVersion" -ForegroundColor Green
} else {
    Write-Host " ✗ Not found" -ForegroundColor Red
    $allGood = $false
}

# Check mypy
Write-Host "  Checking mypy..." -NoNewline
if (Get-Command mypy -ErrorAction SilentlyContinue) {
    $mypyVersion = mypy --version 2>&1
    Write-Host " ✓ $mypyVersion" -ForegroundColor Green
} else {
    Write-Host " ✗ Not found" -ForegroundColor Red
    $allGood = $false
}

# Check bandit
Write-Host "  Checking bandit..." -NoNewline
if (Get-Command bandit -ErrorAction SilentlyContinue) {
    $banditVersion = bandit --version 2>&1 | Select-Object -First 1
    Write-Host " ✓ $banditVersion" -ForegroundColor Green
} else {
    Write-Host " ✗ Not found" -ForegroundColor Red
    $allGood = $false
}

# Check pre-commit
Write-Host "  Checking pre-commit..." -NoNewline
if (Get-Command pre-commit -ErrorAction SilentlyContinue) {
    $precommitVersion = pre-commit --version 2>&1
    Write-Host " ✓ $precommitVersion" -ForegroundColor Green
} else {
    Write-Host " ✗ Not found" -ForegroundColor Red
    $allGood = $false
}

Write-Host ""
if ($allGood) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ✓ Setup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Run pre-commit checks:" -ForegroundColor White
    Write-Host "     pre-commit run --all-files" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  2. Start coding! Available commands:" -ForegroundColor White
    Write-Host "     ruff check src/          # Lint code" -ForegroundColor Gray
    Write-Host "     ruff format src/         # Format code" -ForegroundColor Gray
    Write-Host "     mypy src/                # Type check" -ForegroundColor Gray
    Write-Host "     pytest tests/ -v         # Run tests" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "  ⚠ Setup completed with warnings" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Some tools failed to install. Try:" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "Documentation: See CLAUDE.md for full commands" -ForegroundColor Cyan
Write-Host ""
