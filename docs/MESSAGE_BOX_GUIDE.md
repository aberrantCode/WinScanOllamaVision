# Message Box Usage Guide

## Overview

All message boxes in the application should use the centralized functions in `src/ui/styles.py`. These functions ensure:
- **Consistent dark mode theming** across all dialogs
- **Single point of maintenance** for future styling changes
- **Type-safe parameters** with clear documentation
- **Automatic theme detection** from user settings

## Available Functions

### 1. `show_information()` - Information Messages

Simple informational message with blue "i" icon and OK button.

```python
from ui.styles import show_information

# Basic usage
show_information(self, "Success", "File saved successfully!")

# With detailed expandable text
show_information(
    self,
    "Analysis Complete",
    "Processed 150 files",
    detailed_text="Errors: 0\nWarnings: 3\nSkipped: 2"
)
```

### 2. `show_warning()` - Warning Messages

Warning message with yellow warning icon and OK button.

```python
from ui.styles import show_warning

show_warning(self, "Invalid Input", "Please enter a valid file path.")

# With details
show_warning(
    self,
    "Permission Denied",
    "Cannot write to this directory",
    detailed_text="Path: C:\\Windows\\System32\nError: Access denied"
)
```

### 3. `show_critical()` - Error Messages

Critical error message with red X icon and OK button.

```python
from ui.styles import show_critical

show_critical(self, "Database Error", "Failed to connect to database.")

# With exception details
try:
    risky_operation()
except Exception as e:
    show_critical(
        self,
        "Operation Failed",
        "An unexpected error occurred",
        detailed_text=str(e)
    )
```

### 4. `show_question()` - Customizable Questions

Question dialog with customizable buttons and default button.

```python
from PyQt6.QtWidgets import QMessageBox
from ui.styles import show_question

# Simple Yes/No (No is default for safety)
reply = show_question(self, "Confirm Delete", "Delete this file?")
if reply == QMessageBox.StandardButton.Yes:
    delete_file()

# Yes/No with Yes as default
reply = show_question(
    self,
    "Save Changes",
    "Save before closing?",
    default_button=QMessageBox.StandardButton.Yes
)

# Custom buttons: Save/Discard/Cancel
reply = show_question(
    self,
    "Unsaved Changes",
    "You have unsaved changes. What would you like to do?",
    buttons=QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel,
    default_button=QMessageBox.StandardButton.Save
)

if reply == QMessageBox.StandardButton.Save:
    save_changes()
elif reply == QMessageBox.StandardButton.Discard:
    close_without_saving()
# else: Cancel - do nothing
```

### 5. `show_confirm()` - Simple Boolean Confirmation

Convenience wrapper for simple yes/no confirmations that returns a boolean.

```python
from ui.styles import show_confirm

# Simple confirmation (returns True/False)
if show_confirm(self, "Delete File", "Are you sure you want to delete this file?"):
    delete_file()

# Confirm is default (unsafe action should default to cancel)
if show_confirm(
    self,
    "Purge Database",
    "This will delete ALL data. Are you sure?",
    default_cancel=True  # This is the default
):
    purge_database()

# Custom button text (not yet implemented, use show_question for now)
```

### 6. `show_message()` - Universal Function

Low-level function that all others use. Supports all parameters.

```python
from PyQt6.QtWidgets import QMessageBox
from ui.styles import show_message

# Full customization
reply = show_message(
    parent=self,
    title="Complex Dialog",
    text="Main message here",
    icon=QMessageBox.Icon.Question,
    buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    default_button=QMessageBox.StandardButton.No,
    detailed_text="Optional expandable details"
)
```

## Migration from Direct QMessageBox Calls

### Before (Direct QMessageBox - NOT RECOMMENDED)

```python
from PyQt6.QtWidgets import QMessageBox

# Don't do this - styling inconsistent
QMessageBox.information(self, "Title", "Message")

# Don't do this - no dark mode theming
QMessageBox.warning(self, "Title", "Message")

# Don't do this - bright blue buttons in dark mode
reply = QMessageBox.question(
    self,
    "Confirm",
    "Are you sure?",
    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    QMessageBox.StandardButton.No
)
```

### After (Centralized Functions - RECOMMENDED)

```python
from ui.styles import show_information, show_warning, show_question

# Do this - consistent theming
show_information(self, "Title", "Message")

# Do this - proper dark mode support
show_warning(self, "Title", "Message")

# Do this - themed buttons in dark mode
reply = show_question(
    self,
    "Confirm",
    "Are you sure?",
    default_button=QMessageBox.StandardButton.No
)
```

## Benefits

1. **Dark Mode Support**: Buttons automatically use appropriate dark colors
2. **Consistency**: All dialogs look the same across the application
3. **Maintainability**: Change styling in one place (`_get_message_box_stylesheet()`)
4. **Type Safety**: Clear parameter types and return values
5. **Documentation**: Built-in docstrings with examples

## Implementation Details

### Theme Detection

The functions automatically detect dark mode from user settings:

```python
config = ConfigManager()
is_dark = config.get_bool("Appearance", "dark_mode", default=False)
colors = ThemeManager.get_colors(is_dark)
```

### Stylesheet Application

All message boxes use `ThemeManager.get_colors()` for consistency:

```python
QMessageBox QPushButton {
    background-color: {colors["bg_tertiary"]};  # Dark blue in dark mode
    color: {colors["text_primary"]};
    /* ... */
}

QMessageBox QPushButton:default {
    background-color: {colors["accent"]};  # Accent blue for primary action
    color: white;
    font-weight: 600;
}
```

## Current Status

✅ **Completed**:
- Centralized message box functions created
- Dark mode theming implemented
- Type checking passes
- Documentation complete

⚠️ **Optional Future Work**:
- Migrate existing `QMessageBox` direct calls to use centralized functions
  - Note: Global `ThemeManager` stylesheet already applies to all message boxes
  - Migration is for code consistency, not visual fixes
- Add custom button text support (e.g., "Delete" instead of "Yes")
- Add icon customization (custom icons beyond standard set)

## Testing

To test the new functions, run the application in dark mode and trigger various message boxes to verify:
1. Background is dark blue (#0B1120)
2. Text is light (#E0E0E0)
3. Buttons are dark blue (#1F2A40) with proper hover states
4. Default buttons use accent blue (#3B82F6)
5. All buttons are clearly visible and not bright blue
