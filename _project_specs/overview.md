# Project Overview

## Vision

WinScanLLM is a PyQt6 desktop application that simplifies document scanning and metadata extraction using multiple LLM providers. It provides a unified interface for analyzing scanned documents (images/PDFs) and organizing them based on extracted metadata.

## Goals

- [x] Multi-provider LLM support (Ollama, Claude CLI, Gemini CLI)
- [x] Provider abstraction with unified interface
- [x] Incremental/cached analysis to avoid re-processing
- [x] Local-first storage (AppData for databases, logs, settings)
- [x] PyQt6 GUI with progress tracking
- [ ] Comprehensive test coverage (unit + integration)
- [ ] Pre-commit hooks and CI/CD
- [ ] Automated file organization workflows
- [ ] Batch processing optimizations

## Non-Goals

- Web-based interface (desktop only)
- Cloud storage integration (local-first)
- OCR engine (uses LLMs for text extraction)
- Direct file manipulation (output to separate directories)

## Success Metrics

- Successfully process 100+ page scans per session
- Provider abstraction allows adding new LLMs in <2 hours
- Test coverage >80% across all modules
- Zero credential leaks or security vulnerabilities
- Incremental analysis reduces re-processing by >90%
