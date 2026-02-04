"""
Test script for the restructured Analysis Status Window
Demonstrates the 2-tab layout with Collection Status placeholder and File Analysis Grid
"""

import sys
from PyQt6.QtWidgets import QApplication
from src.analysis_status_window import AnalysisStatusWindow
from src.config_manager import ConfigManager


def main():
    """Test the Analysis Status Window"""
    app = QApplication(sys.argv)

    # Create config manager
    config = ConfigManager()

    # Create and show the Analysis Status Window
    window = AnalysisStatusWindow(config_manager=config)
    window.show()

    print("Analysis Status Window opened successfully!")
    print(f"- Window title: {window.windowTitle()}")
    print(f"- Minimum size: {window.minimumSize().width()}x{window.minimumSize().height()}")
    print(f"- Number of tabs: {window.tabs.count()}")
    print(f"  Tab 1: {window.tabs.tabText(0)}")
    print(f"  Tab 2: {window.tabs.tabText(1)}")
    print("\nYou can:")
    print("- Click between the two tabs")
    print("- Click the Refresh button")
    print("- Explore the File Analysis Grid (tab 2)")
    print("- Close the window when done")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
