"""
Manual Test Script for Prompt Optimization Feature

This script helps manually verify the prompt optimization feature works correctly.

Usage:
    python scripts/test_prompt_optimization_manual.py

Expected behavior:
1. Settings window opens with LLM Provider tab active
2. Two prompt editors are visible with "Optimize Prompt" buttons
3. Clicking "Optimize Prompt" should:
   - Show confirmation dialog
   - Show progress dialog
   - Send request to active LLM provider
   - Show comparison dialog with before/after
   - Allow user to accept or cancel changes

Test cases to verify:
- Empty prompt shows warning
- Successful optimization shows comparison dialog
- User can edit optimized prompt before accepting
- Cancel preserves original prompt
- Accept updates the prompt text
- Works with all 3 providers: Ollama, Claude CLI, Gemini CLI
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PyQt6.QtWidgets import QApplication, QMessageBox
from settings_window_enhanced import EnhancedSettingsWindow


def run_manual_test():
    """Run manual test of prompt optimization"""
    app = QApplication(sys.argv)

    print("\n" + "=" * 60)
    print("PROMPT OPTIMIZATION FEATURE - MANUAL TEST")
    print("=" * 60)
    print("\nTest Instructions:")
    print("1. Navigate to 'LLM Provider' tab")
    print("2. Check your active provider in the dropdown")
    print("3. Try optimizing the 'Document Validation Prompt':")
    print("   - Click 'Optimize Prompt' button")
    print("   - Confirm when asked")
    print("   - Wait for optimization (10-60 seconds)")
    print("   - Review before/after comparison")
    print("   - You can edit the optimized version")
    print("   - Accept or Cancel")
    print("\n4. Test with empty prompt (should show warning)")
    print("5. Test error handling (disconnect network/stop provider)")
    print("\nProvider Requirements:")
    print("- Ollama: Service must be running (http://localhost:11434)")
    print("- Claude CLI: 'claude' command must be available")
    print("- Gemini CLI: 'gemini' command must be available")
    print("\n" + "=" * 60)

    # Show info dialog with test instructions
    QMessageBox.information(
        None,
        "Prompt Optimization Test",
        "Settings window will open.\n\n"
        "Navigate to 'LLM Provider' tab and test the 'Optimize Prompt' button.\n\n"
        "Check console for test instructions.",
    )

    # Create and show settings window
    window = EnhancedSettingsWindow()

    # Navigate to LLM Provider tab (index 1)
    window.tab_widget.setCurrentIndex(1)

    window.show()

    # Run event loop
    exit_code = app.exec()

    print("\n" + "=" * 60)
    print("Test completed. Window closed.")
    print("=" * 60 + "\n")

    return exit_code


if __name__ == "__main__":
    sys.exit(run_manual_test())
