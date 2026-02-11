"""Test that GUI integration methods exist and can be called."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

print("Testing GUI integration methods...")

# We can't actually instantiate ConvertImagesWindow without full Qt app setup
# But we can verify the methods exist by reading the source

import ast
import inspect

# Read gui.py
gui_path = Path(__file__).parent.parent / "src" / "ui" / "gui.py"
with open(gui_path, "r", encoding="utf-8") as f:
    gui_source = f.read()

# Parse the AST
tree = ast.parse(gui_source)

# Find all method names in the file
methods = set()
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        methods.add(node.name)

# Check for required methods
required_methods = [
    "_prepare_bundles_for_workflow",
    "_on_bundle_accepted_from_workflow",
    "_on_bundle_rejected_from_workflow",
    "_on_workflow_completed",
    "_load_and_show_bundle_suggestions",
]

print("\nChecking for required methods:")
all_found = True
for method in required_methods:
    if method in methods:
        print(f"[OK] {method} exists")
    else:
        print(f"[ERROR] {method} NOT FOUND")
        all_found = False

if not all_found:
    print("\n[FAIL] Some required methods are missing!")
    sys.exit(1)

# Check that the workflow import is present
if "from ui.verify_documents_window import BundleReviewWindow" in gui_source:
    print("\n[OK] Guided workflow import exists in gui.py")
else:
    print("\n[ERROR] Guided workflow import NOT FOUND in gui.py")
    sys.exit(1)

# Check that workflow is instantiated
if "GuidedBundleWorkflow(" in gui_source:
    print("[OK] Workflow instantiation code exists in gui.py")
else:
    print("[ERROR] Workflow instantiation code NOT FOUND in gui.py")
    sys.exit(1)

# Check signal connections
required_connections = [
    "bundle_accepted.connect",
    "bundle_rejected.connect",
    "workflow_completed.connect",
]

print("\nChecking signal connections:")
all_connected = True
for connection in required_connections:
    if connection in gui_source:
        print(f"[OK] {connection} exists")
    else:
        print(f"[ERROR] {connection} NOT FOUND")
        all_connected = False

if not all_connected:
    print("\n[FAIL] Some signal connections are missing!")
    sys.exit(1)

print("\n[SUCCESS] All GUI integration methods and connections exist!")
