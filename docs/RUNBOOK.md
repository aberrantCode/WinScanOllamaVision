# WinScanLLM Runbook

Operational procedures for deploying, monitoring, and troubleshooting WinScanLLM.

## Table of Contents

- [Deployment Procedures](#deployment-procedures)
- [Application Architecture](#application-architecture)
- [Monitoring and Health Checks](#monitoring-and-health-checks)
- [Common Issues and Fixes](#common-issues-and-fixes)
- [Database Management](#database-management)
- [Rollback Procedures](#rollback-procedures)
- [Emergency Contacts](#emergency-contacts)

## Deployment Procedures

### Pre-Deployment Checklist

- [ ] All tests passing (`python run_tests.py tests/ -v`)
- [ ] Code coverage ≥90% (`--cov-fail-under=90` in pytest config)
- [ ] Type checking passes (`mypy src/ --ignore-missing-imports`)
- [ ] Security scan clean (`.\scripts\security-check.ps1`)
- [ ] Pre-commit hooks passing (`pre-commit run --all-files`)
- [ ] Database migrations tested on copy of production data
- [ ] Release notes prepared
- [ ] Backup of current production databases

### Deployment Steps

#### 1. Prepare Release

```powershell
# Verify clean working directory
git status

# Ensure on correct branch
git checkout master
git pull origin master

# Tag release version
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0
```

#### 2. Create Distribution

```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install build dependencies
pip install build wheel

# Create distribution packages
python -m build

# Distribution files created in dist/
# - winscan_llm-0.1.0.tar.gz
# - winscan_llm-0.1.0-py3-none-any.whl
```

#### 3. Install on Target System

```powershell
# On target machine, create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install from wheel
pip install winscan_llm-0.1.0-py3-none-any.whl

# Or install from requirements
pip install -r requirements.txt
```

#### 4. Post-Deployment Verification

```powershell
# Verify application starts
python src/main.py

# Check database migrations applied
# Databases are in %APPDATA%/WinScanLLM/
ls $env:APPDATA\WinScanLLM\*.db

# Verify logging working
# Logs are in %APPDATA%/WinScanLLM/logs/
Get-Content $env:APPDATA\WinScanLLM\logs\app.log -Tail 20

# Test basic functionality
# - Open settings window
# - Run analysis on test directory
# - Create test bundle
```

### Rollback Procedure

If deployment fails or causes issues:

```powershell
# 1. Stop application (if running)
# Close all WinScanLLM windows

# 2. Restore database backups
Copy-Item "$env:APPDATA\WinScanLLM\backup\*.db" "$env:APPDATA\WinScanLLM\"

# 3. Checkout previous version
git checkout v0.0.9  # Previous stable version

# 4. Reinstall dependencies
pip install -r requirements.txt

# 5. Verify application starts
python src/main.py

# 6. Notify users of rollback
```

## Application Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                     │
│  (PyQt6 Windows: gui.py, analysis_status_window.py, etc.)  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     Service Layer                            │
│  (analysis_service, bundling_service, file_service)         │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
┌────────▼────────┐         ┌────────▼────────┐
│  Database Layer │         │  LLM Providers  │
│  (analysis_db,  │         │  (ollama, claude,│
│   metadata_db)  │         │   gemini)       │
└─────────────────┘         └─────────────────┘
```

### Data Storage Locations

**Application Data Directory:** `%APPDATA%\WinScanLLM\`

```
%APPDATA%\WinScanLLM\
├── settings.ini           # User configuration
├── analysis.db            # Analysis results and provenance
├── metadata.db            # Document metadata (normalized)
└── logs\
    └── app.log            # Application logs (rotating, 10MB max, 5 backups)
```

### Database Schema

**analysis.db:**
- `schema_version` - Migration tracking (current: v16)
- `analysis_results` - LLM analysis provenance (provider, model, timestamps)
- `image_files` - Registered image files with hashes and status
- `pdf_files` - Generated PDF bundles

**metadata.db:**
- `schema_version` - Migration tracking (current: v13)
- `metadata` - Normalized document metadata (company, type, date, etc.)
- `archived_metadata` - Historical metadata versions
- `field_history` - Tracking changes to metadata fields

### Configuration File

**Location:** `%APPDATA%\WinScanLLM\settings.ini`

**Key sections:**
```ini
[LLMProvider]
active_provider = ollama

[Ollama]
model = qwen2.5-vl
base_url = http://localhost:11434
timeout = 300

[ClaudeCLI]
enabled = true
command_template = claude -m %%MODEL%% %%IMAGE_PATHS%% -p "%%PROMPT%%"
default_models = claude-3-5-sonnet-20241022,claude-3-5-haiku-20241022

[GeminiCLI]
enabled = true
command_template = gemini -m %%MODEL%% %%IMAGE_PATHS%% -p "%%PROMPT%%"
default_models = gemini-2.0-flash-exp,gemini-1.5-pro

[AutoAnalysis]
enabled = true
batch_size = 10

[SourceDirectories]
directories = ["C:\\Users\\username\\Pictures\\Scans"]

[OutputDirectory]
path = C:\Users\username\Documents\Organized
strategy = organized_subfolder
```

## Monitoring and Health Checks

### Application Logs

**Location:** `%APPDATA%\WinScanLLM\logs\app.log`

**Log levels:**
- `DEBUG` - Detailed diagnostic information
- `INFO` - General informational messages
- `WARNING` - Warning messages (non-critical issues)
- `ERROR` - Error messages (operation failed but app continues)
- `CRITICAL` - Critical errors (app may need to shut down)

**Checking logs:**
```powershell
# View recent logs
Get-Content $env:APPDATA\WinScanLLM\logs\app.log -Tail 50

# Search for errors
Select-String -Path $env:APPDATA\WinScanLLM\logs\app.log -Pattern "ERROR|CRITICAL"

# Monitor logs in real-time
Get-Content $env:APPDATA\WinScanLLM\logs\app.log -Wait
```

### Health Check Procedures

#### 1. Database Connectivity

```powershell
# Check database files exist
Test-Path $env:APPDATA\WinScanLLM\analysis.db
Test-Path $env:APPDATA\WinScanLLM\metadata.db

# Check database integrity
sqlite3 $env:APPDATA\WinScanLLM\analysis.db "PRAGMA integrity_check;"
sqlite3 $env:APPDATA\WinScanLLM\metadata.db "PRAGMA integrity_check;"
```

#### 2. LLM Provider Connectivity

**Ollama:**
```powershell
# Check Ollama server running
curl http://localhost:11434/api/tags
```

**Claude CLI:**
```powershell
# Verify Claude CLI installed and authenticated
claude --version
```

**Gemini CLI:**
```powershell
# Verify Gemini CLI installed
gemini --version
```

#### 3. Disk Space

```powershell
# Check available disk space
Get-PSDrive C | Select-Object Used,Free

# Check AppData directory size
Get-ChildItem $env:APPDATA\WinScanLLM -Recurse | Measure-Object -Property Length -Sum
```

#### 4. Performance Metrics

Monitor from **Analytics & Details** window in application:
- Total images analyzed
- Average processing time per image
- Cache hit rate (should be >0% for repeated analyses)
- Error rate (should be <5%)

## Common Issues and Fixes

### Issue 1: Application Won't Start

**Symptoms:**
- Application crashes on startup
- Error: "LoggingService not initialized"

**Diagnosis:**
```powershell
# Check if AppData directory exists
Test-Path $env:APPDATA\WinScanLLM

# Check permissions
icacls $env:APPDATA\WinScanLLM
```

**Fix:**
```powershell
# Create AppData directory
New-Item -ItemType Directory -Path $env:APPDATA\WinScanLLM -Force

# Create logs directory
New-Item -ItemType Directory -Path $env:APPDATA\WinScanLLM\logs -Force

# Restart application
python src/main.py
```

### Issue 2: Database Migration Failures

**Symptoms:**
- Error: "Migration X failed"
- Database schema version mismatch

**Diagnosis:**
```powershell
# Check current schema version
sqlite3 $env:APPDATA\WinScanLLM\analysis.db "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1;"
```

**Fix:**
```powershell
# Backup databases first
Copy-Item "$env:APPDATA\WinScanLLM\*.db" "$env:APPDATA\WinScanLLM\backup\"

# Option 1: Re-run migrations (automatic on startup)
python src/main.py

# Option 2: Manual migration rollback (if needed)
# Restore from backup
Copy-Item "$env:APPDATA\WinScanLLM\backup\analysis.db" "$env:APPDATA\WinScanLLM\analysis.db"
```

### Issue 3: LLM Provider Connection Failures

**Symptoms:**
- Analysis fails with "Provider connection error"
- Timeout errors

**Diagnosis:**
```powershell
# Test Ollama connectivity
curl http://localhost:11434/api/tags

# Check Claude CLI authentication
claude --version

# Check logs for errors
Select-String -Path $env:APPDATA\WinScanLLM\logs\app.log -Pattern "Provider.*error"
```

**Fix (Ollama):**
```powershell
# Restart Ollama service (Windows)
# Ollama runs as a system service - may need admin rights

# Check if Ollama is running
Get-Process ollama -ErrorAction SilentlyContinue

# If not running, start Ollama application
# It will auto-start the service
```

**Fix (Claude/Gemini CLI):**
```powershell
# Re-authenticate
claude auth login
# Or for Gemini
gemini auth login
```

### Issue 4: High Memory Usage

**Symptoms:**
- Application consuming >2GB memory
- Slow performance

**Diagnosis:**
```powershell
# Check memory usage
Get-Process python | Select-Object Name, WS, PM

# Check database size
Get-ChildItem $env:APPDATA\WinScanLLM\*.db | Select-Object Name, Length
```

**Fix:**
```powershell
# Vacuum databases to reclaim space
sqlite3 $env:APPDATA\WinScanLLM\analysis.db "VACUUM;"
sqlite3 $env:APPDATA\WinScanLLM\metadata.db "VACUUM;"

# Clear old log files
Remove-Item $env:APPDATA\WinScanLLM\logs\app.log.* -Force

# Restart application
```

### Issue 5: UI Not Updating After Changes

**Symptoms:**
- Metadata changes not reflected in UI
- File grid not refreshing

**Diagnosis:**
- Check logs for database errors
- Verify database connection not locked

**Fix:**
```powershell
# Close all WinScanLLM windows

# Check for stale lock files
Get-ChildItem $env:APPDATA\WinScanLLM\*.db-journal

# Remove lock files if present (only when app closed!)
Remove-Item $env:APPDATA\WinScanLLM\*.db-journal -Force

# Restart application
python src/main.py
```

### Issue 6: Tests Failing on Windows

**Symptoms:**
- `PermissionError` when running tests
- Database file locked errors

**Fix:**
```powershell
# Close handlers in test fixtures
# Already implemented in test_logging_service.py

# Ensure no other processes using databases
Get-Process | Where-Object {$_.Modules.ModuleName -match "analysis.db|metadata.db"}

# Run tests with verbose output to identify exact failure
python run_tests.py tests/ -v --tb=short
```

## Database Management

### Backup Procedures

**Manual backup:**
```powershell
# Create backup directory
New-Item -ItemType Directory -Path $env:APPDATA\WinScanLLM\backup -Force

# Backup databases
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item $env:APPDATA\WinScanLLM\analysis.db "$env:APPDATA\WinScanLLM\backup\analysis_$timestamp.db"
Copy-Item $env:APPDATA\WinScanLLM\metadata.db "$env:APPDATA\WinScanLLM\backup\metadata_$timestamp.db"
```

**Automated backup script:**
```powershell
# Save as backup-databases.ps1
$backupDir = "$env:APPDATA\WinScanLLM\backup"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

New-Item -ItemType Directory -Path $backupDir -Force

Copy-Item "$env:APPDATA\WinScanLLM\analysis.db" "$backupDir\analysis_$timestamp.db"
Copy-Item "$env:APPDATA\WinScanLLM\metadata.db" "$backupDir\metadata_$timestamp.db"

# Keep only last 7 days of backups
Get-ChildItem $backupDir -Filter "*.db" |
    Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} |
    Remove-Item
```

### Database Maintenance

**Vacuum databases (reclaim space):**
```powershell
sqlite3 $env:APPDATA\WinScanLLM\analysis.db "VACUUM;"
sqlite3 $env:APPDATA\WinScanLLM\metadata.db "VACUUM;"
```

**Analyze databases (optimize queries):**
```powershell
sqlite3 $env:APPDATA\WinScanLLM\analysis.db "ANALYZE;"
sqlite3 $env:APPDATA\WinScanLLM\metadata.db "ANALYZE;"
```

**Check integrity:**
```powershell
sqlite3 $env:APPDATA\WinScanLLM\analysis.db "PRAGMA integrity_check;"
sqlite3 $env:APPDATA\WinScanLLM\metadata.db "PRAGMA integrity_check;"
```

### Migration Management

**Current schema versions:**
- `analysis.db`: Migration 16 (schema refactoring)
- `metadata.db`: Migration 13

**Check migration status:**
```sql
-- In sqlite3
SELECT * FROM schema_version ORDER BY version DESC;
```

**Rollback migration (emergency only):**
```powershell
# STOP: This is destructive. Backup first!

# Restore from pre-migration backup
Copy-Item "$env:APPDATA\WinScanLLM\backup\analysis_pre_migration_16.db" "$env:APPDATA\WinScanLLM\analysis.db"

# Delete migration record
sqlite3 $env:APPDATA\WinScanLLM\analysis.db "DELETE FROM schema_version WHERE version = 16;"
```

## Rollback Procedures

### Application Rollback

**Scenario:** New version causes critical issues

```powershell
# 1. Identify last known good version
git tag -l

# 2. Backup current databases
Copy-Item "$env:APPDATA\WinScanLLM\*.db" "$env:APPDATA\WinScanLLM\backup_before_rollback\"

# 3. Checkout previous version
git checkout v0.0.9

# 4. Reinstall dependencies
pip install -r requirements.txt

# 5. Test application
python src/main.py

# 6. If successful, update deployment
git tag -a v0.0.9-hotfix -m "Hotfix rollback"
```

### Database Rollback

**Scenario:** Migration corrupted data

```powershell
# 1. Close application
# Close all WinScanLLM windows

# 2. Restore from backup
Copy-Item "$env:APPDATA\WinScanLLM\backup\analysis_20250210.db" "$env:APPDATA\WinScanLLM\analysis.db"
Copy-Item "$env:APPDATA\WinScanLLM\backup\metadata_20250210.db" "$env:APPDATA\WinScanLLM\metadata.db"

# 3. Verify restoration
sqlite3 $env:APPDATA\WinScanLLM\analysis.db "SELECT COUNT(*) FROM analysis_results;"

# 4. Restart application
python src/main.py
```

### Configuration Rollback

**Scenario:** Configuration change breaks functionality

```powershell
# 1. Backup current config
Copy-Item "$env:APPDATA\WinScanLLM\settings.ini" "$env:APPDATA\WinScanLLM\settings.ini.backup"

# 2. Restore from version control
git show HEAD:data/settings.ini > "$env:APPDATA\WinScanLLM\settings.ini"

# 3. Restart application
python src/main.py
```

## Emergency Contacts

### Development Team

- **Project Lead:** [GitHub: aberrantCode](https://github.com/aberrantCode)
- **Issues:** [GitHub Issues](https://github.com/aberrantCode/WinScanLLM/issues)
- **Discussions:** [GitHub Discussions](https://github.com/aberrantCode/WinScanLLM/discussions)

### Escalation Procedures

1. **Check existing issues:** Search [GitHub Issues](https://github.com/aberrantCode/WinScanLLM/issues)
2. **Check logs:** Review `%APPDATA%\WinScanLLM\logs\app.log`
3. **Create issue:** Include:
   - Error message from logs
   - Steps to reproduce
   - System information (Python version, OS version)
   - Database schema version
   - LLM provider being used

### Critical Issue Response

**Database corruption:**
1. Stop application immediately
2. Backup corrupted database
3. Restore from last known good backup
4. Report issue with corrupted database attached

**Data loss:**
1. DO NOT make further changes
2. Backup current state
3. Contact development team immediately
4. Provide database backups for analysis

**Security issue:**
1. Report privately via GitHub Security Advisory
2. Do not disclose publicly until patched
3. Include proof-of-concept if available

## Maintenance Schedule

### Daily
- Monitor application logs for errors
- Check disk space usage

### Weekly
- Backup databases
- Review error rates in Analytics window
- Update LLM models if needed

### Monthly
- Vacuum databases (reclaim space)
- Clean old log files (>30 days)
- Review and archive old backups
- Check for dependency updates (`pip list --outdated`)

### Quarterly
- Full security audit (`.\scripts\security-check.ps1`)
- Review and update documentation
- Performance benchmarking
- Dependency vulnerability scan (`pip-audit`)

## Performance Tuning

### Database Optimization

```powershell
# Create indices for common queries (already in schema.py)
# Run ANALYZE to update query planner statistics
sqlite3 $env:APPDATA\WinScanLLM\analysis.db "ANALYZE;"
sqlite3 $env:APPDATA\WinScanLLM\metadata.db "ANALYZE;"
```

### LLM Provider Optimization

**Ollama:**
- Use smaller models for faster processing (`qwen2.5-vl` is good balance)
- Increase batch size in settings if system has sufficient RAM
- Monitor GPU usage if using GPU acceleration

**Claude/Gemini CLI:**
- Use Haiku models for faster responses (`claude-3-5-haiku-20241022`)
- Implement retry logic for rate limiting
- Cache responses when possible

### UI Performance

- Enable progressive loading for large file lists
- Use virtual scrolling for grids with >100 items
- Defer image loading until visible in viewport

## Appendix

### Useful SQL Queries

**Count analyses by provider:**
```sql
SELECT provider_name, COUNT(*) as count
FROM analysis_results
GROUP BY provider_name
ORDER BY count DESC;
```

**Find images with errors:**
```sql
SELECT img.file_path, ar.response_text
FROM image_files img
JOIN analysis_results ar ON img.id = ar.image_file_id
WHERE ar.had_error = 1;
```

**Average processing time by model:**
```sql
SELECT model_name, AVG(processing_time_ms) as avg_time_ms
FROM analysis_results
WHERE had_error = 0 AND processing_time_ms > 0
GROUP BY model_name
ORDER BY avg_time_ms;
```

**Cache hit rate:**
```sql
SELECT
    COUNT(DISTINCT image_file_id) as total_images,
    SUM(CASE WHEN analysis_count > 1 THEN 1 ELSE 0 END) as cached_images,
    ROUND(100.0 * SUM(CASE WHEN analysis_count > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as cache_hit_rate
FROM (
    SELECT image_file_id, COUNT(*) as analysis_count
    FROM analysis_results
    GROUP BY image_file_id
);
```

### Log File Rotation

Logs automatically rotate at 10MB with 5 backups retained:
```
app.log       (current, 0-10MB)
app.log.1     (previous, 10MB)
app.log.2     (older, 10MB)
app.log.3     (older, 10MB)
app.log.4     (older, 10MB)
app.log.5     (oldest, 10MB)
```

Total maximum log storage: 60MB

### Configuration File Schema

Full configuration reference: See `src/config/config_manager.py:_create_default_config()`
