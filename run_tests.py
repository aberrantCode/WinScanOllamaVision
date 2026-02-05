#!/usr/bin/env python
"""
Test runner that ensures src/ is in Python path before running pytest.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py tests/config # Run specific directory
    python run_tests.py -k provider  # Run tests matching pattern
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# Now import and run pytest
import pytest

if __name__ == "__main__":
    # Run pytest with arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else ["tests/", "-v"]
    exit_code = pytest.main(args)
    sys.exit(exit_code)
