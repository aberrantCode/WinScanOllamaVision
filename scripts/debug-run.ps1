#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Debug script to clean build artifacts, verify dependencies, and run the application.

.DESCRIPTION
    This script performs a complete clean build and run cycle:
    1. Removes all Python cache files and build artifacts
    2. Optionally reinstalls dependencies
    3. Runs the application with proper error handling

.PARAMETER SkipDependencies
    Skip dependency verification/installation step

.PARAMETER CleanOnly
    Only clean cache files, don't run the application

.EXAMPLE
    .\scripts\debug-run.ps1
    Clean cache and run the application

.EXAMPLE
    .\scripts\debug-run.ps1 -CleanOnly
    Only clean cache files

.EXAMPLE
    .\scripts\debug-run.ps1 -SkipDependencies
    Clean and run without checking dependencies
#>

param(
    [switch]$SkipDependencies,
    [switch]$CleanOnly
)

# Color output functions
function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

# Change to project root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
Set-Location $projectRoot

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          WinScanLLM Debug Clean Build & Run Script           ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Clean all cache and build artifacts
Write-Step "Step 1: Cleaning all cache and build artifacts..."

# Remove __pycache__ directories
$pycacheDirs = Get-ChildItem -Path . -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue
if ($pycacheDirs) {
    foreach ($dir in $pycacheDirs) {
        Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Success "Removed $($pycacheDirs.Count) __pycache__ directories"
} else {
    Write-Success "No __pycache__ directories found"
}

# Remove .pyc and .pyo files
$compiledFiles = Get-ChildItem -Path . -File -Recurse -Include "*.pyc","*.pyo" -ErrorAction SilentlyContinue
if ($compiledFiles) {
    foreach ($file in $compiledFiles) {
        Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
    }
    Write-Success "Removed $($compiledFiles.Count) compiled Python files (.pyc, .pyo)"
} else {
    Write-Success "No compiled Python files found"
}

# Remove .pytest_cache directories
$pytestCache = Get-ChildItem -Path . -Directory -Recurse -Filter ".pytest_cache" -ErrorAction SilentlyContinue
if ($pytestCache) {
    foreach ($dir in $pytestCache) {
        Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Success "Removed $($pytestCache.Count) .pytest_cache directories"
} else {
    Write-Success "No .pytest_cache directories found"
}

# Remove build and dist directories (if they exist)
$buildDirs = Get-ChildItem -Path . -Directory -Filter "build" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notlike "*\venv\*" }
$distDirs = Get-ChildItem -Path . -Directory -Filter "dist" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notlike "*\venv\*" }
$eggDirs = Get-ChildItem -Path . -Directory -Filter "*.egg-info" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notlike "*\venv\*" }

$artifactCount = 0
foreach ($dir in ($buildDirs + $distDirs + $eggDirs)) {
    Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $artifactCount++
}

if ($artifactCount -gt 0) {
    Write-Success "Removed $artifactCount build artifact directories"
} else {
    Write-Success "No build artifacts found"
}

Write-Host ""

# Exit if clean-only mode
if ($CleanOnly) {
    Write-Success "Cache cleanup complete! (Clean-only mode - not running application)"
    Write-Host ""
    exit 0
}

# Step 2: Verify Python and virtual environment
Write-Step "Step 2: Verifying Python environment..."

# Check if venv exists
if (-not (Test-Path "venv")) {
    Write-Error-Custom "Virtual environment not found at ./venv"
    Write-Warning-Custom "Please create a virtual environment first:"
    Write-Host "  python -m venv venv" -ForegroundColor Yellow
    Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Check if virtual environment is activated
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if ($pythonPath -and ($pythonPath -like "*venv*")) {
    Write-Success "Virtual environment is activated"
} else {
    Write-Warning-Custom "Virtual environment is not activated"
    Write-Host "Attempting to activate..." -ForegroundColor Yellow

    # Try to activate
    $activateScript = ".\venv\Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        & $activateScript
        Write-Success "Virtual environment activated"
    } else {
        Write-Error-Custom "Could not find activation script"
        exit 1
    }
}

# Get Python version
try {
    $pythonVersion = python --version 2>&1
    Write-Success "Using Python: $pythonVersion"
} catch {
    Write-Error-Custom "Python is not available"
    exit 1
}

Write-Host ""

# Step 3: Verify/Install dependencies
if (-not $SkipDependencies) {
    Write-Step "Step 3: Verifying dependencies..."

    if (Test-Path "requirements.txt") {
        Write-Host "Installing/updating dependencies from requirements.txt..." -ForegroundColor Yellow
        python -m pip install --quiet --upgrade pip
        python -m pip install --quiet -r requirements.txt

        if ($LASTEXITCODE -eq 0) {
            Write-Success "Dependencies verified/installed successfully"
        } else {
            Write-Error-Custom "Failed to install dependencies"
            exit 1
        }
    } else {
        Write-Warning-Custom "No requirements.txt found, skipping dependency check"
    }

    Write-Host ""
} else {
    Write-Step "Step 3: Skipping dependency verification (--SkipDependencies flag set)"
    Write-Host ""
}

# Step 4: Run the application
Write-Step "Step 4: Running application..."
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                   Starting WinScanLLM...                       ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

# Run the application and capture exit code
try {
    python src/main.py
    $exitCode = $LASTEXITCODE

    Write-Host ""
    if ($exitCode -eq 0) {
        Write-Success "Application exited normally (exit code: $exitCode)"
    } else {
        Write-Warning-Custom "Application exited with code: $exitCode"
    }
} catch {
    Write-Error-Custom "Failed to run application: $_"
    exit 1
}

Write-Host ""
exit $exitCode
