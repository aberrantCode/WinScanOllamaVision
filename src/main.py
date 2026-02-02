import sys
import os
import traceback
from PyQt6.QtWidgets import QApplication
from gui import StartupWindow
from appdata_manager import initialize_appdata

# Import style sheet
from style import stylesheet

log_file_path = "app.log"

def log_message(message):
    """Appends a message to the log file."""
    with open(log_file_path, "a") as log_file:
        log_file.write(f"{message}\n")

if __name__ == "__main__":
    # Clear previous log file
    if os.path.exists(log_file_path):
        os.remove(log_file_path)

    try:
        log_message("Application starting...")

        # Initialize AppData directory (settings and database)
        log_message("Initializing AppData directory...")
        settings_path, db_path = initialize_appdata()
        log_message(f"AppData initialized - Settings: {settings_path}, Database: {db_path}")

        app = QApplication(sys.argv)
        log_message("QApplication instance created.")
        
        app.setStyleSheet(stylesheet)
        log_message("Stylesheet applied.")
        
        log_message("Creating StartupWindow...")
        startup_window = StartupWindow()
        log_message("StartupWindow instance created.")
        
        log_message("Showing StartupWindow...")
        startup_window.show()
        log_message("StartupWindow.show() called.")
        
        log_message("Entering QApplication event loop...")
        exit_code = app.exec()
        log_message(f"Application exited with code {exit_code}.")
        sys.exit(exit_code)

    except Exception as e:
        log_message("An unhandled exception occurred:")
        log_message(traceback.format_exc())
        sys.exit(1)

