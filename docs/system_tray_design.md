# System Tray Integration Design

## Overview

System tray integration allows the app to run in background, showing status and providing quick actions without keeping the main window open.

---

## Tray Icon

### Icon Design

**Primary Icon**: `assets/tray_icon.png`
- 16x16px for system tray (high DPI: 32x32px)
- Simple, recognizable silhouette
- Based on app icon but simplified for small size
- Monochrome or simple color for visibility across themes

**Suggested Icon**: Scanner outline or document with checkmark

### Icon States

1. **Idle** (`tray_icon.png`):
   - Gray/neutral color
   - No analysis running
   - App waiting for user action

2. **Analyzing** (`tray_icon_analyzing.png`):
   - Animated or blue color
   - Analysis in progress
   - Optional: Overlay with progress indicator

3. **Attention Needed** (`tray_icon_attention.png`):
   - Orange/amber color
   - Error occurred or user input needed
   - Badge with "!" or number

4. **Success** (`tray_icon_success.png`):
   - Green color
   - Task completed successfully
   - Auto-reverts to Idle after 5 seconds

---

## Settings Integration

### Settings → Appearance Tab

```
┌─────────────────────────────────────────┐
│ System Tray                             │
│                                         │
│ [✓] Enable system tray icon            │
│                                         │
│ [ ] Minimize to tray                   │
│     When minimized, hide window and    │
│     show icon in system tray           │
│                                         │
│ [ ] Close to tray                      │
│     Clicking [X] minimizes to tray     │
│     instead of closing app             │
│                                         │
│ [✓] Show notifications                 │
│     Display tray notifications for     │
│     completed tasks                    │
│                                         │
│ Start with Windows:                    │
│ [ ] Start minimized to tray            │
│                                         │
└─────────────────────────────────────────┘
```

---

## User Interactions

### Minimize to Tray

**Trigger**: User clicks minimize button AND "Minimize to tray" setting enabled

**Behavior**:
1. Main window hides (not minimized to taskbar)
2. Tray icon appears (if not already visible)
3. Optional balloon notification: "WinScanLLM minimized to tray"
4. Taskbar button disappears
5. App continues running in background

### Close to Tray

**Trigger**: User clicks [X] close button AND "Close to tray" setting enabled

**Behavior**:
1. If "Close to tray" ENABLED:
   - Same as minimize to tray
   - First time: Show balloon: "App will run in background. Right-click tray icon to quit."
2. If "Close to tray" DISABLED:
   - Show confirmation dialog: "Quit WinScanLLM?"
   - If Yes: Exit app completely
   - If No: Cancel close

### Click Tray Icon

**Single Left-Click**:
- If window hidden: Restore and show window
- If window visible: Bring to front and focus
- If window minimized: Restore to previous size

**Double-Click**:
- Same as single click (for consistency)

**Right-Click**:
- Show context menu (see below)

---

## Tray Context Menu

### Standard Menu (Idle State)

```
┌─────────────────────────────┐
│ WinScanLLM                  │  ← App name (bold, disabled)
├─────────────────────────────┤
│ Open Window             ↵   │  ← Default action
│ Convert Scans...            │
│ Convert PDFs...             │
│ Settings...                 │
├─────────────────────────────┤
│ Analysis                    │  ← Submenu
│   ├─ Start Analysis         │
│   ├─ View Last Results      │
│   └─ Cancel                 │  (disabled when not running)
├─────────────────────────────┤
│ About WinScanLLM            │
│ Quit                        │  ← Always exits (bypasses "close to tray")
└─────────────────────────────┘
```

### Menu During Analysis

```
┌─────────────────────────────┐
│ WinScanLLM                  │
│ Analyzing... 23/47 pages    │  ← Status (disabled, gray)
├─────────────────────────────┤
│ Open Window             ↵   │
│ Convert Scans...            │  (disabled during analysis)
│ Convert PDFs...             │  (disabled during analysis)
│ Settings...                 │
├─────────────────────────────┤
│ Analysis                    │
│   ├─ View Progress...       │
│   ├─ Cancel Analysis        │  (enabled)
│   └─ Start Analysis         │  (disabled)
├─────────────────────────────┤
│ About WinScanLLM            │
│ Quit                        │
└─────────────────────────────┘
```

---

## Notifications

### Analysis Complete

**When**: AnalysisService finishes scanning

**Notification**:
```
┌─────────────────────────────────────┐
│ [Icon] WinScanLLM                   │
│                                     │
│ Analysis Complete                   │
│ 47 pages analyzed in 2m 15s        │
│                                     │
│ [View Results]    [Dismiss]         │
└─────────────────────────────────────┘
```

**Click Behavior**:
- Click notification: Open main window + navigate to Convert Scans
- Click [View Results]: Same as above
- Click [Dismiss]: Close notification

### PDF Creation Complete

**When**: PDF generation finishes in ConvertImagesWindow

**Notification**:
```
┌─────────────────────────────────────┐
│ [Icon] WinScanLLM                   │
│                                     │
│ PDFs Created                        │
│ 3 documents saved successfully      │
│                                     │
│ [Open Folder]    [Dismiss]          │
└─────────────────────────────────────┘
```

**Click Behavior**:
- Click [Open Folder]: Open output directory in Explorer
- Click [Dismiss]: Close notification

### Error Notification

**When**: Critical error occurs (LLM connection failed, etc.)

**Notification**:
```
┌─────────────────────────────────────┐
│ [Icon] WinScanLLM                   │
│                                     │
│ Analysis Failed                     │
│ Could not connect to LLM service    │
│                                     │
│ [Open Settings]    [Dismiss]        │
└─────────────────────────────────────┘
```

---

## Background Operation

### Scenarios Where Tray is Useful

1. **Long Analysis**:
   - User starts analysis on 100+ pages
   - Minimizes to tray to free up screen space
   - Works on other tasks
   - Gets notification when complete

2. **Monitoring**:
   - App runs in background
   - Auto-analyzes new scans when they appear
   - User gets notified of results
   - Never needs to open main window

3. **Quick Access**:
   - User frequently scans documents
   - Keeps app in tray for quick access
   - Right-click → Convert Scans
   - Faster than launching app each time

---

## Implementation Details

### PyQt6 System Tray

```python
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction

class SystemTrayManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.config = ConfigManager()

        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self.main_window)
        self.tray_icon.setIcon(QIcon("assets/tray_icon.png"))
        self.tray_icon.setToolTip("WinScanLLM - Idle")

        # Create context menu
        self._create_menu()

        # Connect signals
        self.tray_icon.activated.connect(self._on_tray_clicked)

        # Show icon if enabled
        if self.config.get_bool("SystemTray", "enabled", True):
            self.tray_icon.show()

    def _create_menu(self):
        menu = QMenu()

        # App name (disabled header)
        app_name = QAction("WinScanLLM", self.main_window)
        app_name.setEnabled(False)
        menu.addAction(app_name)
        menu.addSeparator()

        # Open window
        open_action = QAction("Open Window", self.main_window)
        open_action.triggered.connect(self.main_window.show)
        menu.addAction(open_action)

        # Convert actions
        convert_scans = QAction("Convert Scans...", self.main_window)
        convert_scans.triggered.connect(self._on_convert_scans)
        menu.addAction(convert_scans)

        convert_pdfs = QAction("Convert PDFs...", self.main_window)
        convert_pdfs.triggered.connect(self._on_convert_pdfs)
        menu.addAction(convert_pdfs)

        # Settings
        settings_action = QAction("Settings...", self.main_window)
        settings_action.triggered.connect(self._on_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        # Quit
        quit_action = QAction("Quit", self.main_window)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)

    def _on_tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single left-click
            if self.main_window.isVisible():
                self.main_window.activateWindow()
            else:
                self.main_window.show()

    def show_notification(self, title, message, icon_type="info"):
        if not self.config.get_bool("SystemTray", "show_notifications", True):
            return

        icon = QSystemTrayIcon.MessageIcon.Information
        if icon_type == "warning":
            icon = QSystemTrayIcon.MessageIcon.Warning
        elif icon_type == "error":
            icon = QSystemTrayIcon.MessageIcon.Critical

        self.tray_icon.showMessage(title, message, icon, 5000)

    def update_icon(self, state="idle"):
        """Update icon based on app state"""
        icons = {
            "idle": "assets/tray_icon.png",
            "analyzing": "assets/tray_icon_analyzing.png",
            "attention": "assets/tray_icon_attention.png",
            "success": "assets/tray_icon_success.png"
        }
        self.tray_icon.setIcon(QIcon(icons.get(state, icons["idle"])))

    def update_tooltip(self, text):
        """Update hover tooltip"""
        self.tray_icon.setToolTip(f"WinScanLLM - {text}")
```

---

## Window Close Handling

### Override closeEvent in StartupWindow

```python
def closeEvent(self, event):
    """Handle window close button"""
    close_to_tray = self.config_manager.get_bool("SystemTray", "close_to_tray", False)

    if close_to_tray and self.tray_manager.tray_icon.isVisible():
        # Minimize to tray instead of closing
        event.ignore()
        self.hide()

        # First-time notification
        if not self.config_manager.get_bool("SystemTray", "tray_hint_shown", False):
            self.tray_manager.show_notification(
                "WinScanLLM",
                "App minimized to system tray. Right-click icon to quit.",
                "info"
            )
            self.config_manager.set_setting("SystemTray", "tray_hint_shown", "true")
    else:
        # Normal close (with confirmation if work in progress)
        if self._has_unsaved_work():
            reply = QMessageBox.question(
                self,
                "Quit WinScanLLM?",
                "Work in progress will be lost. Are you sure?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        event.accept()
        QApplication.quit()
```

---

## Asset Requirements

Need to create 4 icon files:

1. **tray_icon.png** (16x16 and 32x32)
   - Neutral/gray color
   - Idle state

2. **tray_icon_analyzing.png** (16x16 and 32x32)
   - Blue color or animated
   - Analysis in progress

3. **tray_icon_attention.png** (16x16 and 32x32)
   - Orange/amber color
   - Error or attention needed

4. **tray_icon_success.png** (16x16 and 32x32)
   - Green color
   - Task completed

---

## User Experience Flow

### First-Time User

1. Launches app (no tray icon by default on first run)
2. Goes to Settings → Appearance
3. Enables "Minimize to tray" and/or "Close to tray"
4. Clicks [X] to close
5. Sees notification: "App minimized to system tray..."
6. Icon appears in tray
7. Can right-click for menu or left-click to restore

### Power User

1. Enables "Start minimized to tray" in settings
2. Adds app to Windows startup
3. App runs in background on boot
4. Auto-analyzes scans as they appear
5. User gets notifications when complete
6. Can quickly access via tray menu

---

## Testing Checklist

- [ ] Tray icon appears when enabled
- [ ] Icon changes state during analysis
- [ ] Left-click restores window
- [ ] Right-click shows context menu
- [ ] Menu actions work correctly
- [ ] "Minimize to tray" hides window
- [ ] "Close to tray" prevents quit
- [ ] Notifications appear and are clickable
- [ ] "Quit" from tray menu fully exits
- [ ] Settings persist across restarts
- [ ] Multiple instances handled correctly
- [ ] Works across Windows 10/11
