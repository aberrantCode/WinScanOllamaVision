# Running WinScanLLM

This document explains how to run the WinScanLLM application.

## Quick Start

### Using PowerShell (Recommended for Windows)

```powershell
.\scripts\Start-App.ps1
```

### Using Bash (Git Bash or WSL)

```bash
./scripts/start-app.sh
```

## What the Scripts Do

Both scripts perform the following steps:

1. **Clear Python Caches**
   - Remove all `__pycache__` directories
   - Delete all `.pyc` (bytecode) files
   - Delete all `.pyo` (optimized bytecode) files
   - Remove `.pytest_cache`, `.mypy_cache`, `.ruff_cache`

2. **Verify Virtual Environment**
   - Check that `venv/` exists
   - Display Python version being used

3. **Activate Virtual Environment**
   - Use the venv's Python interpreter directly

4. **Run Application**
   - Execute `src/main.py`
   - Display exit code

## Manual Execution

If you prefer to run the application manually:

```powershell
# PowerShell
.\venv\Scripts\Activate.ps1
python src\main.py
```

```bash
# Bash
source venv/Scripts/activate  # or venv/bin/activate on Linux/Mac
python src/main.py
```

## Troubleshooting

### Virtual Environment Not Found

If the scripts report that the virtual environment is not found:

```powershell
# Create virtual environment
python -m venv venv

# Install dependencies
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Module Import Errors

If you see `ModuleNotFoundError` errors, reinstall dependencies:

```powershell
.\venv\Scripts\Activate.ps1
pip install --force-reinstall --no-cache-dir -r requirements.txt
```

### Permission Denied (Bash Script)

If you get "Permission denied" when running the bash script:

```bash
chmod +x scripts/start-app.sh
./scripts/start-app.sh
```

## Cache Clearing Benefits

Clearing Python caches before running helps with:

- ✅ Ensuring code changes are picked up immediately
- ✅ Avoiding stale bytecode issues after file modifications
- ✅ Resolving import errors caused by moved/renamed modules
- ✅ Clean startup for debugging purposes
- ✅ Preventing version mismatch issues

## Execution Policy (PowerShell)

If PowerShell blocks script execution, you may need to allow it:

```powershell
# Check current policy
Get-ExecutionPolicy

# Allow local scripts (run as Administrator)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# Or run directly with bypass (one-time)
PowerShell -ExecutionPolicy Bypass -File .\scripts\Start-App.ps1
```

## Development Mode

For development with automatic cache clearing, you can use the scripts in your development workflow:

```powershell
# After making code changes
.\scripts\Start-App.ps1

# The script automatically clears caches before each run
```

## Command Line Arguments

To pass arguments to the application through the scripts:

```powershell
# PowerShell - modify the script or run directly:
.\venv\Scripts\python.exe src\main.py --console --console-level DEBUG

# Bash - modify the script or run directly:
./venv/Scripts/python.exe src/main.py --console --console-level DEBUG
```

## Available Arguments

```
--console              Enable console logging output
--console-level LEVEL  Set console logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
```

Example:
```powershell
.\venv\Scripts\python.exe src\main.py --console --console-level INFO
```
