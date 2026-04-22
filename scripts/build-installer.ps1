<#
.SYNOPSIS
    Build a WinScanLLM Windows installer locally.

.DESCRIPTION
    Writes src/__version__.py from -Version, runs PyInstaller against
    installer/WinScanLLM.spec to produce dist/WinScanLLM/, then runs
    Inno Setup to wrap it into installer/Output/WinScanLLM-Setup-<ver>.exe.

.PARAMETER Version
    Version string for the build (PEP 440 compatible). Defaults to "0.0.0-dev".

.EXAMPLE
    .\scripts\build-installer.ps1 -Version "0.1.0-dev"
#>

param(
    [string]$Version = "0.0.0-dev"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "==> Writing src/__version__.py ($Version)" -ForegroundColor Cyan
Set-Content -Path (Join-Path $repoRoot "src\__version__.py") `
            -Value "__version__ = `"$Version`"`n" `
            -Encoding UTF8

Push-Location $repoRoot
try {
    Write-Host "==> Running PyInstaller" -ForegroundColor Cyan
    & pyinstaller installer/WinScanLLM.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed ($LASTEXITCODE)" }

    $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $iscc)) {
        throw "Inno Setup 6 not found at $iscc. Install from https://jrsoftware.org/isdl.php"
    }

    Write-Host "==> Running Inno Setup" -ForegroundColor Cyan
    & $iscc "/DAppVersion=$Version" "installer\WinScanLLM.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed ($LASTEXITCODE)" }

    $out = Join-Path $repoRoot "installer\Output\WinScanLLM-Setup-$Version.exe"
    if (Test-Path $out) {
        Write-Host ""
        Write-Host "Built: $out" -ForegroundColor Green
        Write-Host "Size:  $((Get-Item $out).Length) bytes" -ForegroundColor Green
    } else {
        Write-Warning "Expected installer not found at $out"
    }
}
finally {
    Pop-Location
}
