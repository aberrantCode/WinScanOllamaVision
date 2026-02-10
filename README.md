# WinScanLLM

[![CI](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/ci.yml/badge.svg)](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/aberrantCode/WinScanOllamaVision/branch/master/graph/badge.svg)](https://codecov.io/gh/aberrantCode/WinScanOllamaVision)
[![CodeQL](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/codeql.yml/badge.svg)](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/codeql.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**WinScanLLM** is a PyQt6 desktop application for intelligent document scanning and analysis using multi-provider LLM integration. It automatically extracts metadata from scanned documents (invoices, receipts, statements), organizes files, and creates searchable PDFs with minimal user intervention.

## 🎯 Key Features

### Multi-Provider LLM Support
- **Ollama** - Local Ollama server integration (default: `qwen2.5-vl`)
- **Claude CLI** - Anthropic's Claude models via CLI
- **Gemini CLI** - Google's Gemini models via CLI
- Provider-agnostic architecture with unified interface

### Intelligent Document Analysis
- **Automatic metadata extraction** - Company name, document type, date, page numbers
- **Metadata normalization** - Consistent data formatting across providers
- **Caching system** - SHA-256 file hashing for incremental analysis
- **Error handling** - Robust error recovery with detailed logging
- **Batch processing** - Configurable batch sizes for large document sets

### Document Organization
- **Smart bundling** - Groups related pages into multi-page PDFs
- **Guided workflow** - Step-by-step document review and correction
- **Flexible output** - Customizable naming and directory structure
- **PDF generation** - Creates searchable PDFs with embedded text layers

### User Interface
- **Analytics & Details** - Comprehensive analysis statistics and document tracking
- **File Details Grid** - Filterable, sortable view of all analyzed images
- **Image Details** - Per-image metadata viewing and editing
- **PDF Details** - Generated bundle tracking with page counts
- **Theme support** - Light and dark mode with persistent preferences
- **Settings management** - Comprehensive configuration UI

### Data Management
- **Normalized database schema** - Separation of analysis provenance and document metadata
- **Metadata history** - Track changes to document metadata over time
- **Archived metadata** - Preserve previous analysis results
- **Foreign key constraints** - Data integrity with CASCADE operations
- **Migration system** - Automated schema updates (current: v16)

## 🏗️ Architecture

WinScanLLM follows a clean, modular architecture with clear separation of concerns:

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

### Package Structure

```
src/
├── main.py              # Application entry point
├── config/              # Configuration management
│   ├── config_manager.py
│   └── appdata_manager.py
├── db/                  # Database layer with repository pattern
│   ├── analysis_db.py       # Analysis results facade
│   ├── metadata_db.py       # Document metadata facade
│   ├── connection.py        # Database connection management
│   ├── schema.py            # Schema migrations (current: v16)
│   └── repositories/        # Repository implementations
├── services/            # Business logic and orchestration
│   ├── analysis_service.py  # Document analysis orchestration
│   ├── bundling_service.py  # PDF creation and bundling
│   ├── file_service.py      # File operations
│   ├── logging_service.py   # Centralized logging (singleton)
│   ├── analysis_queue.py    # Analysis queue management
│   └── metadata_normalizer.py  # Metadata normalization
├── ui/                  # PyQt6 user interface components
│   ├── gui.py
│   ├── analysis_status_window.py
│   ├── file_details_grid.py
│   ├── settings_window_enhanced.py
│   └── style.py
└── llm_providers/       # LLM provider implementations
    ├── base_provider.py
    ├── provider_factory.py
    ├── ollama_provider.py
    ├── claude_cli_provider.py
    └── gemini_cli_provider.py
```

### Data Storage

**Location:** `%APPDATA%\WinScanLLM\` (Windows)

```
%APPDATA%\WinScanLLM\
├── settings.ini           # User configuration
├── analysis.db            # Analysis results and provenance (Migration 16)
├── metadata.db            # Document metadata (Migration 13)
└── logs\
    └── app.log            # Application logs (rotating, 10MB max, 5 backups)
```

**Database Schema:**
- **analysis.db** - LLM analysis provenance (provider, model, timestamps, processing metrics)
- **metadata.db** - Normalized document metadata (company, type, date, confidence scores)

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (tested on 3.11, 3.12, 3.13)
- **Git** for version control
- **LLM Provider** (at least one):
  - Ollama server (recommended for local processing)
  - Claude CLI (requires Anthropic API key)
  - Gemini CLI (requires Google API key)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/aberrantCode/WinScanLLM.git
   cd scan_organization
   ```

2. **Create virtual environment**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1  # PowerShell (Windows)
   # Or for cmd.exe: .\venv\Scripts\activate.bat
   ```

3. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Install pre-commit hooks** (for contributors)
   ```powershell
   pre-commit install
   pre-commit install --hook-type commit-msg
   ```

5. **Verify installation**
   ```powershell
   .\scripts\verify-tooling.ps1
   ```

### LLM Provider Setup

#### Option 1: Ollama (Recommended)

1. Download and install Ollama from [ollama.com](https://ollama.com/)
2. Pull a vision model:
   ```powershell
   ollama pull qwen2.5-vl
   ```
3. Ollama server starts automatically on `http://localhost:11434`

#### Option 2: Claude CLI

1. Install Claude CLI: https://www.npmjs.com/package/@anthropic-ai/claude-cli
2. Authenticate:
   ```powershell
   claude auth login
   ```

#### Option 3: Gemini CLI

1. Install Gemini CLI: https://ai.google.dev/gemini-api/docs/cli
2. Authenticate with your Google API key

### Running the Application

```powershell
python src/main.py
```

## 📖 Usage

### First-Time Setup

1. **Launch application** - `python src/main.py`
2. **Open Settings** - Click "Settings" button
3. **Configure LLM Provider:**
   - Select provider (Ollama, Claude CLI, or Gemini CLI)
   - Choose model (e.g., `qwen2.5-vl` for Ollama)
   - Test connection
4. **Add Source Directories:**
   - Click "Add Directory"
   - Select folders containing scanned images
5. **Configure Output:**
   - Set output directory for organized PDFs
   - Choose output strategy (organized subfolder or custom path)

### Document Analysis Workflow

1. **Scan & Analyze**
   - Click "Analyze Files" in main window
   - Application scans configured directories
   - Images analyzed using selected LLM provider
   - Results cached by file hash for efficiency

2. **Review & Edit Metadata**
   - Open "Analytics & Details" window
   - View extracted metadata in "Image Details" tab
   - Edit company, document type, date, page numbers
   - Changes saved to metadata database

3. **Bundle Documents**
   - Click "Guided Bundle Workflow"
   - Review suggested document groupings
   - Adjust page selections and metadata
   - Generate PDF bundle
   - View results in "PDF Details" tab

### Analytics & Monitoring

**Analytics & Details Window:**
- **Analytics tab** - Processing statistics, average times, error rates
- **Image Details tab** - Per-image metadata with filtering and sorting
- **PDF Details tab** - Generated bundle tracking with page counts

**Features:**
- Double-click PDF to open in default viewer
- Export data to CSV
- Filter by company, document type, date range
- Sort by any column
- Theme switching (light/dark)

## 🧪 Development

### Running Tests

```powershell
# Run all tests with coverage
python run_tests.py tests/

# Run specific test module
python run_tests.py tests/config/

# Run tests matching pattern
python run_tests.py tests/ -k "metadata"

# Verbose output
python run_tests.py tests/ -v
```

**Test Coverage:** Currently at **89%** with 629 tests passing

### Code Quality

```powershell
# Type checking
mypy src/ --ignore-missing-imports

# Linting
ruff check src/

# Formatting
ruff format src/

# Security scanning
.\scripts\security-check.ps1
bandit -r src/
```

### Pre-Commit Hooks

Pre-commit hooks automatically run:
- ruff (linting and formatting)
- mypy (type checking)
- bandit (security scanning)
- File validation (YAML, JSON, TOML)
- Large file detection (>1MB)
- Merge conflict detection
- Secret detection
- Conventional commit validation

## 📚 Documentation

- **[CONTRIB.md](docs/CONTRIB.md)** - Comprehensive contributor guide with development workflows
- **[RUNBOOK.md](docs/RUNBOOK.md)** - Operational procedures for deployment and troubleshooting
- **[SCRIPTS_REFERENCE.md](docs/SCRIPTS_REFERENCE.md)** - Complete reference for all available scripts
- **[DOCUMENTATION_STATUS.md](docs/DOCUMENTATION_STATUS.md)** - Documentation audit and status
- **[CLAUDE.md](CLAUDE.md)** - Guidelines for Claude Code AI assistant

### Guides

- **[Quick Start](docs/guides/QUICK_START.md)** - Getting started guide
- **[Usage Examples](docs/guides/USAGE_EXAMPLES.md)** - Common usage scenarios
- **[Validation Checklist](docs/guides/VALIDATION_CHECKLIST.md)** - Pre-release validation

### Technical Documentation

- **[Database Schema](docs/features/METADATA_CACHING_IMPLEMENTATION.md)** - Caching and metadata storage
- **[Theme System](docs/THEME_SYSTEM.md)** - UI theming architecture
- **[Analysis DB Query Methods](docs/analysis_db_query_methods.md)** - Database query reference

## 🤝 Contributing

We welcome contributions! Please see [CONTRIB.md](docs/CONTRIB.md) for:
- Development setup and prerequisites
- Testing procedures (TDD workflow)
- Code quality standards
- Security guidelines
- Pull request workflow

### Development Workflow (TDD)

1. **Write test first (RED)** - Test should fail
2. **Implement minimal code (GREEN)** - Test should pass
3. **Refactor (IMPROVE)** - Clean up code
4. **Verify coverage ≥80%** - Run coverage report

### Code Quality Standards

- **Linting:** ruff with pycodestyle, Pyflakes, isort, pep8-naming
- **Type checking:** mypy with strict mode gradually enabled
- **Testing:** pytest with 90% coverage requirement
- **Security:** bandit for security scanning, pip-audit for dependencies
- **Formatting:** ruff format with double quotes, 4-space indentation

### Before Committing

```powershell
# Type check
mypy src/path/to/modified_file.py --ignore-missing-imports

# Run tests
python run_tests.py tests/path/to/relevant_tests.py -v

# Security check
.\scripts\security-check.ps1

# Pre-commit checks (automatic)
git commit -m "feat: your feature description"
```

## 🐛 Troubleshooting

### Common Issues

**Application won't start:**
```powershell
# Create AppData directory
New-Item -ItemType Directory -Path $env:APPDATA\WinScanLLM\logs -Force
```

**LLM provider connection error:**
```powershell
# Test Ollama
curl http://localhost:11434/api/tags

# Re-authenticate Claude
claude auth login

# Re-authenticate Gemini
gemini auth login
```

**Database migration failures:**
```powershell
# Backup databases
Copy-Item "$env:APPDATA\WinScanLLM\*.db" "$env:APPDATA\WinScanLLM\backup\"

# Restart application (migrations run automatically)
python src/main.py
```

**Tests failing with import errors:**
```powershell
# Use run_tests.py instead of pytest directly
python run_tests.py tests/
```

See [RUNBOOK.md](docs/RUNBOOK.md) for comprehensive troubleshooting procedures.

## 📊 Project Status

**Current Version:** 0.1.0 (Development)

**Recent Milestones:**
- ✅ Migration 16 - Schema refactoring (separation of analysis provenance and metadata)
- ✅ Multi-provider LLM support (Ollama, Claude CLI, Gemini CLI)
- ✅ Comprehensive test suite (629 tests, 89% coverage)
- ✅ Documentation overhaul (contributor guide, runbook, scripts reference)
- ✅ Pre-commit hooks with security scanning
- ✅ Theme support (light/dark mode)

**Roadmap:**
- [ ] API reference documentation
- [ ] Database schema ERD diagrams
- [ ] User-facing troubleshooting guide
- [ ] Performance benchmarking and optimization
- [ ] Automated documentation generation from docstrings

See [VERSION_0.1.md](docs/plans/VERSION_0.1.md) and [PROJECT_STATUS.md](docs/plans/PROJECT_STATUS.md) for detailed roadmap.

## 🔐 Security

Security is a top priority. Before committing:

```powershell
# Run security checks
.\scripts\security-check.ps1

# Python security linter
bandit -r src/

# Dependency vulnerability scan
pip-audit
```

**Security features:**
- Pre-commit secret detection
- Staged file validation (no `.env`, `.pem`, `.key` files)
- Hardcoded secret pattern matching
- Regular dependency vulnerability scans

Report security issues privately via [GitHub Security Advisory](https://github.com/aberrantCode/WinScanLLM/security/advisories).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **PyQt6** - Cross-platform GUI framework
- **PyMuPDF** - PDF processing library
- **Ollama** - Local LLM runtime
- **Anthropic Claude** - Advanced language model
- **Google Gemini** - Multimodal AI model
- **ruff** - Fast Python linter and formatter
- **pytest** - Testing framework

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/aberrantCode/WinScanLLM/issues)
- **Discussions:** [GitHub Discussions](https://github.com/aberrantCode/WinScanLLM/discussions)
- **Documentation:** [docs/](docs/)

## 🔗 Links

- **Repository:** https://github.com/aberrantCode/WinScanLLM.git
- **CI/CD:** [GitHub Actions](https://github.com/aberrantCode/WinScanOllamaVision/actions)
- **Code Coverage:** [Codecov](https://codecov.io/gh/aberrantCode/WinScanOllamaVision)
- **Security:** [CodeQL Analysis](https://github.com/aberrantCode/WinScanOllamaVision/security/code-scanning)

---

**Made with ❤️ by [aberrantCode](https://github.com/aberrantCode)**
