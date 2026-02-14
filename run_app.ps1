#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run WinScanLLM application with cache cleanup
.DESCRIPTION
    This script clears Python caches and runs the application using the virtual environment
#>

# Stop on errors
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "WinScanLLM Application Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Step 1: Clear Python cache files
Write-Host "[1/4] Clearing Python cache files..." -ForegroundColor Yellow

# Remove __pycache__ directories
$pycacheDirs = Get-ChildItem -Path "src" -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
$pycacheCount = ($pycacheDirs | Measure-Object).Count
if ($pycacheCount -gt 0) {
    $pycacheDirs | Remove-Item -Recurse -Force
    Write-Host "  ✓ Removed $pycacheCount __pycache__ directories" -ForegroundColor Green
} else {
    Write-Host "  ✓ No __pycache__ directories found" -ForegroundColor Green
}

# Remove .pyc files
$pycFiles = Get-ChildItem -Path "src" -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue
$pycCount = ($pycFiles | Measure-Object).Count
if ($pycCount -gt 0) {
    $pycFiles | Remove-Item -Force
    Write-Host "  ✓ Removed $pycCount .pyc files" -ForegroundColor Green
} else {
    Write-Host "  ✓ No .pyc files found" -ForegroundColor Green
}

# Remove .pyo files (optimized bytecode)
$pyoFiles = Get-ChildItem -Path "src" -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue
$pyoCount = ($pyoFiles | Measure-Object).Count
if ($pyoCount -gt 0) {
    $pyoFiles | Remove-Item -Force
    Write-Host "  ✓ Removed $pyoCount .pyo files" -ForegroundColor Green
} else {
    Write-Host "  ✓ No .pyo files found" -ForegroundColor Green
}

# Remove pytest cache
if (Test-Path ".pytest_cache") {
    Remove-Item ".pytest_cache" -Recurse -Force
    Write-Host "  ✓ Removed pytest cache" -ForegroundColor Green
}

# Remove mypy cache
if (Test-Path ".mypy_cache") {
    Remove-Item ".mypy_cache" -Recurse -Force
    Write-Host "  ✓ Removed mypy cache" -ForegroundColor Green
}

# Remove ruff cache
if (Test-Path ".ruff_cache") {
    Remove-Item ".ruff_cache" -Recurse -Force
    Write-Host "  ✓ Removed ruff cache" -ForegroundColor Green
}

Write-Host ""

# Step 2: Verify virtual environment exists
Write-Host "[2/4] Checking virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "  ✗ Virtual environment not found!" -ForegroundColor Red
    Write-Host "  Please create it first: python -m venv venv" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Virtual environment found" -ForegroundColor Green
Write-Host ""

# Step 3: Activate virtual environment
Write-Host "[3/4] Activating virtual environment..." -ForegroundColor Yellow
$venvPython = Join-Path $ScriptDir "venv\Scripts\python.exe"
$pythonVersion = & $venvPython --version 2>&1
Write-Host "  ✓ Using: $pythonVersion" -ForegroundColor Green
Write-Host ""

# Step 4: Run application
Write-Host "[4/4] Starting WinScanLLM application..." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

try {
    & $venvPython "src\main.py"
    $exitCode = $LASTEXITCODE

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    if ($exitCode -eq 0) {
        Write-Host "Application exited successfully (code: $exitCode)" -ForegroundColor Green
    } else {
        Write-Host "Application exited with code: $exitCode" -ForegroundColor Yellow
    }
    Write-Host "========================================" -ForegroundColor Cyan

    exit $exitCode
} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Error running application:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    exit 1
}
