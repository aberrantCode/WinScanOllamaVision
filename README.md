# WinScanLLM

[![CI](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/ci.yml/badge.svg)](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/aberrantCode/WinScanOllamaVision/branch/master/graph/badge.svg)](https://codecov.io/gh/aberrantCode/WinScanOllamaVision)
[![CodeQL](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/codeql.yml/badge.svg)](https://github.com/aberrantCode/WinScanOllamaVision/actions/workflows/codeql.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

This is a Python-based desktop utility designed to intelligently organize scanned PDF documents using AI-powered analysis. It supports multiple LLM providers (Ollama, Claude CLI, Gemini CLI), inspects local scan folders, combines multi-part PDF documents, renames them based on content extracted by vision models, and moves them to an organized subfolder. The application provides a user interface for previewing, correcting extracted information, and confirming file operations.

## Features:
*   Intelligent grouping of scanned pages into documents based on timestamp and AI validation.
*   Extraction of `Source Company`, `Document Title`, and `Date` using a configurable Ollama vision model.
*   User interface for previewing pages, editing extracted information, and confirming actions.
*   Automatic conversion of TIFF files to PNG for processing.
*   Conversion of multiple PNG/TIFF images into a single, text-searchable PDF.
*   Configurable Ollama model selection from a dropdown, with options to pull (download) remote models and view model details on the Ollama website.
*   Robust error handling at each stage, with user prompts for manual intervention or confirmation.
*   Final confirmation dialog providing explicit control over PDF acceptance and source file deletion.

## Repository:
https://github.com/aberrantCode/WinScanLLM.git

## Setup:

### 1. Install Python
Ensure you have Python 3.8+ installed on your system. You can download it from [python.org](https://www.python.org/downloads/).

### 2. Install Ollama
Download and install Ollama from [ollama.com](https://ollama.com/). Make sure the Ollama server is running locally (it usually starts automatically).

### 3. Install a Vision Model
You need an Ollama vision model for the application to work. The application defaults to `qwen2.5-vl`. You can pull it via the CLI:
```powershell
ollama pull qwen2.5-vl
```
Or, you can pull other vision models like `llava:latest` or `deepseek-ocr` which can also be selected and pulled directly from within the application's UI.

### 4. Clone the Repository
```bash
git clone https://github.com/aberrantCode/WinScanLLM.git
cd WinScanLLM
```

### 5. Install Python Dependencies
It's recommended to use a Python virtual environment:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1   # PowerShell (Windows)
# If using cmd.exe: .\venv\Scripts\activate.bat
```
Then install the required packages:
```powershell
pip install -r requirements.txt
```

## Usage:

### 1. Configure Settings (`settings.ini`)
The application automatically creates a `settings.ini` file in the root directory if it doesn't exist. You can edit this file to customize:
*   `[Ollama]`
    *   `model`: The default Ollama vision model to use (e.g., `qwen2.5-vl`).
    *   `base_url`: The URL of your Ollama server (default: `http://localhost:11434`).
*   `[DocumentProcessing]`
    *   `scan_folder`: The path to your input folder (default: `C:\Users\{username}\Pictures\Scans`).
    *   `organized_subfolder`: The name of the subfolder where organized PDFs will be moved (default: `ORGANIZED`).
    *   `title_keywords`: A comma-separated list of keywords Ollama will use to identify document titles (e.g., `Invoice, Statement, Bill`).
*   `[GUI]`
    *   `window_width`, `window_height`: Initial dimensions of the application window.

### 2. Run the Application
```powershell
python src/gui.py
```

### 3. Workflow:
*   **Model Selection:** Use the dropdown to select your desired Ollama vision model. If a remote model is chosen, click "Pull Model" to download it.
*   **Scan & Group:** Click "Scan & Group New Documents". The application will scan your `scan_folder`, convert any TIFFs to PNGs, and propose groups of pages for documents based on scan timestamps. It will then use Ollama to validate the grouping.
*   **Review & Edit:** For each proposed document, you will see a preview of its pages. Ollama's suggestions for `Company`, `Title`, and `Date` will populate editable text fields. You can correct these manually. You can also uncheck pages you don't want included in the current document group.
*   **Approve & Process:** Click "Approve & Process Document". The application will generate the final PDF.
*   **Final Confirmation:** A dialog will appear, showing the created PDF and any warnings (e.g., page count mismatch, non-searchable PDF). You will have three options:
    1.  **Accept & Delete Source Files**: Keeps the PDF, deletes the original PNGs.
    2.  **Accept & Keep Source Files**: Keeps the PDF, but keeps the original PNGs.
    3.  **Reject & Delete PDF**: Deletes the new PDF, keeps the original PNGs.

## Development:

### Running Tests:
Navigate to the root directory of the project and run:
```powershell
python -m unittest discover tests
```
This will execute all tests in the `tests/` directory.

## Suggested repo layout (proposed)
To make the codebase easier to navigate and maintain, consider organizing `src/` into logical subpackages. This is a non-destructive refactor suggestion — current imports/tests will continue to work, but new files should follow this layout.

Recommended structure:

```
src/
    main.py                      # App startup
    ui/                          # All GUI widgets and windows
        gui.py
        analysis_status_window.py
        settings_window_enhanced.py
        file_details_grid.py
        bundle_widgets.py
        style.py
        styles.py
        style.qss
    services/                    # Business logic and orchestration
        analysis_service.py
        bundling_service.py
        file_processor.py
        phase7_handlers.py
        collection_status_helpers.py
        appdata_manager.py
    db/                          # Database wrappers / persistence
        analysis_db.py
        metadata_db.py
    llm_providers/               # Provider implementations and factory
        base_provider.py
        provider_factory.py
        command_builder.py
        ollama_provider.py
        claude_cli_provider.py
        gemini_cli_provider.py
    config/                      # Configuration helpers
        config_manager.py
    utils/                       # Small helpers/shared utilities
        (move small helpers here)
```

Why this helps:
- Groups UI code away from service logic so reviewers can focus faster.
- Makes provider implementations obvious (all under `llm_providers`).
- Keeps DB wrappers together for schema/transaction changes.
- Simplifies CI and import paths for tests and packaging.

Placement rules (must-follow for new files):
- Source code: add under `src/` (subfolders as above). Avoid new top-level `.py` files in repo root.
- Tests: put new tests in `tests/` following `test_*.py` naming.
- Docs: add Markdown under `docs/`.
- Assets/test data: `assets/` or `data/`.

If you want, I can prepare a small refactor branch that moves files into this structure and updates imports and tests accordingly — should I proceed with a prototype refactor?
