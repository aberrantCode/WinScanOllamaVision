# security-check.ps1
# Run security checks before committing

$ErrorActionPreference = "Stop"
Write-Host "Running security checks..." -ForegroundColor Cyan
Write-Host ""

$hasIssues = $false

# Check .env is not staged
Write-Host "Checking for staged environment files..." -ForegroundColor Yellow
$stagedFiles = git diff --cached --name-only 2>$null
if ($stagedFiles -match '^\.env$|^\.env\.') {
    $envFiles = $stagedFiles | Where-Object { $_ -match '^\.env' -and $_ -notmatch '\.example$' }
    if ($envFiles) {
        Write-Host "  ✗ ERROR: .env file is staged for commit!" -ForegroundColor Red
        Write-Host "    Files: $($envFiles -join ', ')" -ForegroundColor Red
        $hasIssues = $true
    } else {
        Write-Host "  ✓ No .env files staged" -ForegroundColor Green
    }
} else {
    Write-Host "  ✓ No .env files staged" -ForegroundColor Green
}

# Check for common secret patterns in staged files
Write-Host "`nChecking for hardcoded secrets..." -ForegroundColor Yellow
$stagedContent = git diff --cached 2>$null
if ($stagedContent) {
    $secretPatterns = @(
        'password\s*[:=]\s*["\047][^"\047]{8,}["\047]',
        'secret\s*[:=]\s*["\047][^"\047]{8,}["\047]',
        'api_key\s*[:=]\s*["\047][^"\047]{8,}["\047]',
        'apikey\s*[:=]\s*["\047][^"\047]{8,}["\047]',
        'token\s*[:=]\s*["\047][^"\047]{20,}["\047]'
    )

    $foundSecrets = $false
    foreach ($pattern in $secretPatterns) {
        if ($stagedContent -match $pattern) {
            $foundSecrets = $true
            break
        }
    }

    if ($foundSecrets) {
        Write-Host "  ⚠ WARNING: Possible secrets found in staged files" -ForegroundColor Yellow
        Write-Host "    Please verify these are not real secrets" -ForegroundColor Yellow
    } else {
        Write-Host "  ✓ No obvious secrets detected" -ForegroundColor Green
    }
}

# Check for files that shouldn't be committed
Write-Host "`nChecking for sensitive files..." -ForegroundColor Yellow
$sensitivePatterns = @('*.pem', '*.key', '*.p12', 'credentials.json', 'secrets.json')
$foundSensitive = $false
foreach ($pattern in $sensitivePatterns) {
    if ($stagedFiles -like $pattern) {
        Write-Host "  ✗ ERROR: Sensitive file staged: $pattern" -ForegroundColor Red
        $hasIssues = $true
        $foundSensitive = $true
    }
}
if (-not $foundSensitive) {
    Write-Host "  ✓ No sensitive files staged" -ForegroundColor Green
}

# Python dependency check (if pip-audit is available)
Write-Host "`nChecking Python dependencies..." -ForegroundColor Yellow
if (Get-Command pip-audit -ErrorAction SilentlyContinue) {
    try {
        pip-audit --quiet 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ No known vulnerabilities in dependencies" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ pip-audit found issues (run 'pip-audit' for details)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ⚠ pip-audit check failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠ pip-audit not installed (optional: pip install pip-audit)" -ForegroundColor Yellow
}

Write-Host ""
if ($hasIssues) {
    Write-Host "Security checks FAILED! Please fix the issues above." -ForegroundColor Red
    exit 1
} else {
    Write-Host "Security checks complete! ✓" -ForegroundColor Green
    exit 0
}
