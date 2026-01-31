# src/style.py

import os

def load_stylesheet() -> str:
    """Loads the QSS stylesheet from file."""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        qss_path = os.path.join(current_dir, 'style.qss')
        with open(qss_path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print("Warning: style.qss not found. Using default application style.")
        return ""

stylesheet = load_stylesheet()
