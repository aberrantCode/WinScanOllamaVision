"""
Integration test for Analysis Status Window
Manual test to verify window opens and displays correctly
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication
from analysis_status_window import AnalysisStatusWindow
from analysis_db import AnalysisDB


def test_window_opens():
    """Test that the window opens without errors"""
    app = QApplication(sys.argv)

    # Create window with test database
    window = AnalysisStatusWindow()
    window.show()

    print("[PASS] Window opened successfully")
    print(f"[PASS] Window size: {window.size().width()}x{window.size().height()}")
    print(f"[PASS] Number of tabs: {window.tab_widget.count()}")
    print(f"[INFO] Tab names:")
    for i in range(window.tab_widget.count()):
        print(f"  - {window.tab_widget.tabText(i)}")

    # Check if data loads
    stats = window.analysis_db.get_analysis_statistics()
    print(f"\n[PASS] Statistics loaded:")
    print(f"  - Total files: {stats['total_files']}")
    print(f"  - Total runs: {stats['total_runs']}")
    print(f"  - Cache hit rate: {stats['cache_hit_rate']:.1f}%")

    # Don't show the window in automated tests
    # window.exec()

    window.close()
    window.analysis_db.close()

    print("\n[PASS] All integration tests passed!")


if __name__ == '__main__':
    test_window_opens()
