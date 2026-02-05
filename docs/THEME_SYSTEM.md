# Theme System Documentation

## Overview

The application now uses a **centralized theme management system** that ensures consistent styling across all windows, dialogs, and widgets. This eliminates the need for per-widget styling and makes theme changes instant and application-wide.

## Architecture

### ThemeManager (`src/ui/theme_manager.py`)

The `ThemeManager` class provides:

1. **Color Palettes** - Comprehensive color definitions for light and dark themes
2. **Global Stylesheet** - Complete CSS that applies to ALL Qt widgets
3. **Color Access** - Direct access to theme colors when custom styling is needed

### Key Benefits

- ✅ **Single Source of Truth** - All colors and styles defined in one place
- ✅ **Automatic Propagation** - Styles cascade to all child widgets automatically
- ✅ **Easy Theme Switching** - Change from light to dark with one line
- ✅ **Maintainability** - Update styling in one place, affects entire app
- ✅ **Consistency** - No more mismatched colors or styles

## Usage

### Application Startup (Automatic)

The theme is automatically applied at application startup in `main.py`:

```python
from ui.theme_manager import ThemeManager

# Get theme preference from config
is_dark_mode = config_manager.get_setting("Theme", "theme") == "dark"

# Apply theme to entire application
app.setStyleSheet(ThemeManager.get_stylesheet(is_dark_mode))
```

That's it! Every widget in the application now inherits the correct styling.

### Creating New Widgets

**DO NOT** set individual styles on widgets. The global stylesheet handles it:

```python
# ❌ WRONG - Don't do this anymore
button = QPushButton("Click Me")
button.setStyleSheet("background-color: #3B82F6; color: white;")

# ✅ CORRECT - Just create the widget
button = QPushButton("Click Me")
# Styling is automatic via global stylesheet
```

### When Custom Styling IS Needed

If you need colors for custom drawing or special cases:

```python
from ui.theme_manager import ThemeManager

# Get color dictionary
colors = ThemeManager.get_colors(is_dark_mode=True)

# Use colors
custom_widget.set_background(colors["bg_primary"])
painter.setBrush(QColor(colors["accent"]))
```

## Color Palette

### Light Theme

| Color | Hex | Usage |
|-------|-----|-------|
| bg_primary | #FFFFFF | Main background |
| bg_secondary | #F9FAFB | Cards, panels |
| bg_tertiary | #F3F4F6 | Buttons, hover states |
| text_primary | #111827 | Main text |
| text_secondary | #374151 | Secondary text |
| accent | #3B82F6 | Highlights, links |
| border | #E5E7EB | Borders, dividers |

### Dark Theme

| Color | Hex | Usage |
|-------|-----|-------|
| bg_primary | #1E1E1E | Main background |
| bg_secondary | #2D2D2D | Cards, panels |
| bg_tertiary | #3A3A3A | Buttons, hover states |
| text_primary | #E0E0E0 | Main text |
| text_secondary | #B0B0B0 | Secondary text |
| accent | #3B82F6 | Highlights, links |
| border | #4A4A4A | Borders, dividers |

## Styled Widgets

The global stylesheet automatically styles:

- ✅ QWidget, QDialog, QMainWindow
- ✅ QLabel (no borders, transparent backgrounds)
- ✅ QPushButton (all states: normal, hover, pressed, disabled, checked)
- ✅ QLineEdit, QTextEdit, QPlainTextEdit
- ✅ QComboBox (including dropdown items)
- ✅ QCheckBox, QRadioButton
- ✅ QSpinBox, QDoubleSpinBox
- ✅ QSlider
- ✅ QProgressBar
- ✅ QScrollBar (vertical and horizontal)
- ✅ QTableView, QTreeView, QListView
- ✅ QHeaderView
- ✅ QTabWidget, QTabBar
- ✅ QGroupBox
- ✅ QFrame
- ✅ QMenu
- ✅ QToolTip
- ✅ QStatusBar
- ✅ QMessageBox
- ✅ QTextBrowser

## Changing Themes

To add light/dark theme switching to a settings window:

```python
from ui.theme_manager import ThemeManager
from PyQt6.QtWidgets import QApplication

def on_theme_changed(theme_name):
    """Called when user selects light or dark theme"""
    is_dark = (theme_name == "dark")

    # Apply new theme
    app = QApplication.instance()
    app.setStyleSheet(ThemeManager.get_stylesheet(is_dark))

    # Save preference
    config.set_setting("Theme", "theme", theme_name)
```

## Migration Guide

### Old Approach (❌ Don't Use)

```python
widget = QWidget()
widget.setStyleSheet("""
    QWidget {
        background-color: #1E1E1E;
        color: #E0E0E0;
    }
    QLabel {
        color: #B0B0B0;
    }
""")
```

### New Approach (✅ Use This)

```python
widget = QWidget()
# That's it! Styling is automatic.
```

## Special Cases

### Custom QFrame Styling

If you need a frame without borders:

```python
frame = QFrame()
frame.setFrameShape(QFrame.Shape.NoFrame)
# Global stylesheet handles: border: none, background: transparent
```

### Buttons with Special States

The stylesheet handles all button states automatically:

```python
button = QPushButton("Filter")
button.setCheckable(True)  # Toggle button
# Checked state automatically styled with accent color
```

### Table Alternating Row Colors

```python
table = QTableView()
table.setAlternatingRowColors(True)
# Automatic alternating backgrounds
```

## Best Practices

1. **Never use hardcoded colors** - Use theme colors or let stylesheet handle it
2. **Don't override global styles** - Unless absolutely necessary
3. **Test in both themes** - Ensure widgets look good in light and dark modes
4. **Use semantic names** - bg_primary, not "dark_gray"
5. **Keep it simple** - Let the global stylesheet do the work

## Troubleshooting

### Widget not styled correctly

**Problem**: Widget doesn't match theme

**Solution**: Check if widget has `setStyleSheet()` call overriding global theme. Remove it.

### Colors don't match

**Problem**: Hardcoded color somewhere

**Solution**: Search for hex colors (#) in code and replace with theme colors.

### Theme doesn't update

**Problem**: Changed theme but UI didn't update

**Solution**: Theme is applied at app startup. Restart app or call `app.setStyleSheet()` again.

## Future Enhancements

- [ ] Add more theme variants (high contrast, custom colors)
- [ ] Runtime theme switching without restart
- [ ] Theme preview in settings
- [ ] Per-window theme overrides (if needed)

## Summary

The centralized ThemeManager makes styling **simple**, **consistent**, and **maintainable**. Just create your widgets and let the global stylesheet handle the rest!
