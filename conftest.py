"""
Pytest configuration file to ensure src/ is in Python path.

This allows tests to import from config, db, services, etc.
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
