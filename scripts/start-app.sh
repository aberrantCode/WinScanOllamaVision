#!/bin/bash
#
# WinScanLLM Application Launcher (Bash version)
# Clears Python caches and runs the application
#

set -e

echo "========================================"
echo "WinScanLLM Application Launcher"
echo "========================================"
echo ""

# Get project root (one level up from the scripts/ directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Step 1: Clear Python cache files
echo "[1/4] Clearing Python cache files..."

# Remove __pycache__ directories
pycache_count=$(find src -type d -name "__pycache__" 2>/dev/null | wc -l)
if [ "$pycache_count" -gt 0 ]; then
    find src -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo "  ✓ Removed $pycache_count __pycache__ directories"
else
    echo "  ✓ No __pycache__ directories found"
fi

# Remove .pyc files
pyc_count=$(find src -type f -name "*.pyc" 2>/dev/null | wc -l)
if [ "$pyc_count" -gt 0 ]; then
    find src -type f -name "*.pyc" -delete
    echo "  ✓ Removed $pyc_count .pyc files"
else
    echo "  ✓ No .pyc files found"
fi

# Remove .pyo files
pyo_count=$(find src -type f -name "*.pyo" 2>/dev/null | wc -l)
if [ "$pyo_count" -gt 0 ]; then
    find src -type f -name "*.pyo" -delete
    echo "  ✓ Removed $pyo_count .pyo files"
else
    echo "  ✓ No .pyo files found"
fi

# Remove pytest cache
if [ -d ".pytest_cache" ]; then
    rm -rf .pytest_cache
    echo "  ✓ Removed pytest cache"
fi

# Remove mypy cache
if [ -d ".mypy_cache" ]; then
    rm -rf .mypy_cache
    echo "  ✓ Removed mypy cache"
fi

# Remove ruff cache
if [ -d ".ruff_cache" ]; then
    rm -rf .ruff_cache
    echo "  ✓ Removed ruff cache"
fi

echo ""

# Step 2: Verify virtual environment exists
echo "[2/4] Checking virtual environment..."
if [ ! -f "venv/Scripts/python.exe" ] && [ ! -f "venv/bin/python" ]; then
    echo "  ✗ Virtual environment not found!"
    echo "  Please create it first: python -m venv venv"
    exit 1
fi
echo "  ✓ Virtual environment found"
echo ""

# Step 3: Determine Python executable
echo "[3/4] Activating virtual environment..."
if [ -f "venv/Scripts/python.exe" ]; then
    # Windows (Git Bash/WSL)
    VENV_PYTHON="venv/Scripts/python.exe"
elif [ -f "venv/bin/python" ]; then
    # Linux/Mac
    VENV_PYTHON="venv/bin/python"
fi

python_version=$("$VENV_PYTHON" --version 2>&1)
echo "  ✓ Using: $python_version"
echo ""

# Step 4: Run application
echo "[4/4] Starting WinScanLLM application..."
echo "========================================"
echo ""

"$VENV_PYTHON" src/main.py
exit_code=$?

echo ""
echo "========================================"
if [ $exit_code -eq 0 ]; then
    echo "Application exited successfully (code: $exit_code)"
else
    echo "Application exited with code: $exit_code"
fi
echo "========================================"

exit $exit_code
