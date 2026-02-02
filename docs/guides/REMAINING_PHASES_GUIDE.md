# Implementation Guide - Remaining Phases (6-10)

**Current Status:** Phases 1-5 Complete ✅
**Remaining Work:** Phases 6-10 (UI enhancements, testing)
**Estimated Effort:** 15-20 hours

---

## Phase 6: Enhanced Settings Window (5 Tabs)

**Estimated Time:** 4-5 hours
**Complexity:** High (UI complexity, dynamic model loading)

### Objectives
Transform SettingsWindow from simple dialog to tabbed interface with 5 categories:
1. General settings
2. LLM Provider configuration with dynamic panels
3. Multi-directory management
4. Database management and statistics
5. Appearance and theming

### Key Features to Implement

#### Tab 1: General
- **Fields:**
  - Scan folder path (QLineEdit + Browse button)
  - Auto-approval toggle (QCheckBox)
  - Audit trail enable/disable (QCheckBox)
  - Output directory strategy (QComboBox: same_as_source, subdirectory, custom)

#### Tab 2: LLM Provider (Most Complex)
- **Provider Selector:** QComboBox with 3 options (Ollama, Claude CLI, Gemini CLI)
- **Dynamic Panel:** Changes based on selected provider
- **Ollama Panel:**
  - Base URL (QLineEdit)
  - Model dropdown (QComboBox) - populated by querying Ollama API
  - Timeout (QSpinBox)
- **CLI Provider Panel (Claude/Gemini):**
  - Command template (QTextEdit) with variable syntax highlighting
  - Model dropdown (QComboBox) - populated from comma-separated config
  - Timeout (QSpinBox)
- **Prompt Editor:**
  - Expandable QTextEdit for each prompt type
  - [Optimize Prompt] button - sends to active provider for AI improvement
  - [Reset to Default] button - restores original
  - [Save Prompt] button - persists to settings.ini

**Dynamic Model Loading Logic:**
```python
def _on_provider_changed(self, provider_name):
    self.model_dropdown.clear()

    if provider_name == 'ollama':
        # Query Ollama API for models
        try:
            models = self.ollama_service.list_models()
            self.model_dropdown.addItems([m['name'] for m in models])
        except:
            self.model_dropdown.addItem('qwen2.5-vl')  # Fallback

    elif provider_name in ['claude_cli', 'gemini_cli']:
        # Parse from config
        models = self.config.get_provider_models(provider_name)
        self.model_dropdown.addItems(models)
```

**AI Prompt Optimization Logic:**
```python
def _optimize_prompt(self):
    current_prompt = self.prompt_editor.toPlainText()
    provider = self._get_active_provider()

    optimization_request = f"""Improve this prompt for better responses from your model:

{current_prompt}

Provide an optimized version that is:
- More specific and clear
- Better structured
- More likely to get consistent JSON responses
"""

    # Show progress dialog
    result = provider.analyze_images([], optimization_request)

    if result['success']:
        # Show before/after comparison dialog
        self._show_comparison_dialog(current_prompt, result['response'])
```

#### Tab 3: Directories
- **QListWidget** showing all source directories
- **Add button:** Opens QFileDialog to select directory
- **Remove button:** Removes selected directory with confirmation
- **Scan on startup checkbox** for each directory
- Store as JSON array in settings.ini

#### Tab 4: Database
- **Statistics Panel:**
  - Total analyzed pages
  - Cached analyses
  - Average processing time
  - Pending/accepted bundles
  - Database file size
- **Purge Options:**
  - Purge analysis results older than N days
  - Purge completed bundles
  - Purge audit trail
  - Clear orphaned metadata
- **Backup button:** Create database backup with timestamp

#### Tab 5: Appearance
- **Theme selector:** Light/Dark (QComboBox)
- **Default zoom mode (PNG):** Fit to Width/Height/Window/Custom %
- **Default zoom mode (PDF):** Same options
- **System tray options:**
  - Minimize to tray (QCheckBox)
  - Close to tray (QCheckBox)

### Implementation Steps

1. **Convert SettingsWindow to QTabWidget** (1 hour)
   ```python
   class SettingsWindow(QDialog):
       def __init__(self, parent=None):
           super().__init__(parent)
           self.setWindowTitle("Settings")
           self.setGeometry(200, 200, 700, 600)

           layout = QVBoxLayout(self)

           self.tabs = QTabWidget()
           layout.addWidget(self.tabs)

           # Create tabs
           self.tabs.addTab(self._create_general_tab(), "General")
           self.tabs.addTab(self._create_provider_tab(), "LLM Provider")
           self.tabs.addTab(self._create_directories_tab(), "Directories")
           self.tabs.addTab(self._create_database_tab(), "Database")
           self.tabs.addTab(self._create_appearance_tab(), "Appearance")

           # OK/Cancel buttons
           buttons = QDialogButtonBox(
               QDialogButtonBox.StandardButton.Ok |
               QDialogButtonBox.StandardButton.Cancel
           )
           buttons.accepted.connect(self.save_settings)
           buttons.rejected.connect(self.reject)
           layout.addWidget(buttons)
   ```

2. **Implement each tab method** (2 hours)
   - `_create_general_tab()`
   - `_create_provider_tab()` (most complex)
   - `_create_directories_tab()`
   - `_create_database_tab()`
   - `_create_appearance_tab()`

3. **Add dynamic provider switching logic** (1 hour)
   - Connect provider dropdown signal
   - Implement panel swapping
   - Handle model population

4. **Implement prompt optimization** (1 hour)
   - Create optimization dialog
   - Integrate with active provider
   - Show before/after comparison

5. **Testing** (30 minutes)
   - Test all tabs
   - Verify settings save/load
   - Test provider switching

### Files to Modify
- `src/gui.py` (SettingsWindow class, lines 147-656)
- `src/config_manager.py` (possibly add prompt storage methods)

### Commit Message Template
```
feat: Phase 6 - Enhanced Settings Window with 5 tabs

Settings Window Redesign
- Convert to QTabWidget with 5 organized tabs
- General: scan folder, auto-approval, audit trail
- LLM Provider: dynamic panel switching per provider
- Directories: multi-directory management with list
- Database: statistics viewer and purge operations
- Appearance: theme, zoom defaults, system tray

Dynamic Features
- Model dropdown updates when provider changes
- AI-powered prompt optimization with comparison
- Real-time database statistics display
- Directory add/remove with JSON persistence

Implementation
- Provider-specific panels (Ollama vs CLI)
- Command template editor with variable hints
- Backup database with timestamp naming
- Purge operations with confirmation dialogs

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## Phase 7: Document Bundling UI

**Estimated Time:** 3-4 hours
**Complexity:** Medium (UI components, state management)

### Objectives
Add pre-bundling step before ConvertImagesWindow Step 1, showing AI-generated bundle suggestions with confidence scores.

### Key Features to Implement

#### BundleSuggestionCard Widget
```python
class BundleSuggestionCard(QFrame):
    """Card showing a bundle suggestion with metadata and thumbnails"""

    def __init__(self, bundle_data, parent=None):
        super().__init__(parent)
        self.bundle_data = bundle_data
        self._init_ui()

    def _init_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)

        # Header with metadata
        header = QHBoxLayout()

        company_label = QLabel(self.bundle_data.get('company', 'Unknown'))
        company_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        header.addWidget(company_label)

        doc_type = QLabel(self.bundle_data.get('document_type', ''))
        header.addWidget(doc_type)

        date_label = QLabel(self.bundle_data.get('document_date', ''))
        header.addWidget(date_label)

        header.addStretch()

        # Confidence badge
        confidence = self.bundle_data['confidence_score']
        badge_color = self._get_confidence_color(confidence)
        confidence_label = QLabel(f"{confidence:.0%}")
        confidence_label.setStyleSheet(f"""
            background-color: {badge_color};
            color: white;
            padding: 5px 10px;
            border-radius: 3px;
            font-weight: bold;
        """)
        header.addWidget(confidence_label)

        layout.addLayout(header)

        # Thumbnail strip (horizontal)
        thumbnail_scroll = QScrollArea()
        thumbnail_scroll.setWidgetResizable(True)
        thumbnail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        thumbnail_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        thumbnail_scroll.setMaximumHeight(150)

        thumbnail_widget = QWidget()
        thumbnail_layout = QHBoxLayout(thumbnail_widget)

        for file_path in self.bundle_data['file_paths']:
            thumb = self._create_thumbnail(file_path)
            thumbnail_layout.addWidget(thumb)

        thumbnail_scroll.setWidget(thumbnail_widget)
        layout.addWidget(thumbnail_scroll)

        # Action buttons
        button_layout = QHBoxLayout()

        accept_btn = QPushButton("✓ Accept")
        accept_btn.clicked.connect(self.accept_bundle)
        button_layout.addWidget(accept_btn)

        modify_btn = QPushButton("✎ Modify")
        modify_btn.clicked.connect(self.modify_bundle)
        button_layout.addWidget(modify_btn)

        reject_btn = QPushButton("✗ Reject")
        reject_btn.clicked.connect(self.reject_bundle)
        button_layout.addWidget(reject_btn)

        layout.addLayout(button_layout)

    def _get_confidence_color(self, score):
        if score >= 0.8:
            return "#059669"  # Green
        elif score >= 0.5:
            return "#F59E0B"  # Amber
        else:
            return "#DC2626"  # Red
```

#### Pre-Bundling Step in ConvertImagesWindow
Add new step before existing Step 1:
- **Step 0 (new):** Bundle Suggestions
- **Step 1:** Document Stitching (existing, becomes Step 1)
- **Step 2:** Analysis (existing)
- **Step 3:** Ordering (existing)
- **Step 4:** Finalization (existing)

**Logic Flow:**
1. User clicks "Convert Scans"
2. AnalysisService scans directory (if not already done)
3. BundlingService generates recommendations
4. If recommendations exist: show Step 0 (Bundle Suggestions)
5. If no recommendations or user clicks "Review Manually": go to Step 1

#### Implementation in ConvertImagesWindow
```python
def _init_ui(self):
    # ... existing code ...

    # Check if we should show bundling suggestions
    if self._has_bundle_suggestions():
        self._show_bundle_suggestions_step()
    else:
        self._show_step_1()  # Existing stitching step

def _has_bundle_suggestions(self):
    """Check if there are pending bundle suggestions"""
    bundles = self.bundling_service.get_high_confidence_bundles(min_confidence=0.5)
    return len(bundles) > 0

def _show_bundle_suggestions_step(self):
    """Show Step 0: Bundle Suggestions"""
    self._clear_main_area()

    title = QLabel("Bundle Suggestions")
    title.setStyleSheet("font-size: 18pt; font-weight: bold;")
    self.main_layout.addWidget(title)

    subtitle = QLabel("AI-detected document groups. Accept, modify, or review manually.")
    self.main_layout.addWidget(subtitle)

    # Get bundles
    bundles = self.bundling_service.get_bundle_suggestions()

    # Scrollable area with bundle cards
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll_content = QWidget()
    scroll_layout = QVBoxLayout(scroll_content)

    for bundle in bundles:
        card = BundleSuggestionCard(bundle)
        card.accepted.connect(self._on_bundle_accepted)
        card.modified.connect(self._on_bundle_modified)
        card.rejected.connect(self._on_bundle_rejected)
        scroll_layout.addWidget(card)

    scroll_layout.addStretch()
    scroll.setWidget(scroll_content)
    self.main_layout.addWidget(scroll)

    # Action buttons
    button_layout = QHBoxLayout()

    accept_all_btn = QPushButton("Accept All High Confidence")
    accept_all_btn.clicked.connect(self._accept_high_confidence_bundles)
    button_layout.addWidget(accept_all_btn)

    button_layout.addStretch()

    review_manually_btn = QPushButton("Review Manually →")
    review_manually_btn.clicked.connect(self._show_step_1)
    button_layout.addWidget(review_manually_btn)

    self.main_layout.addLayout(button_layout)
```

### Files to Modify
- `src/gui.py` (ConvertImagesWindow class, add BundleSuggestionCard)

### Implementation Steps
1. Create BundleSuggestionCard widget (1 hour)
2. Add Step 0 to ConvertImagesWindow (1 hour)
3. Connect bundle actions (accept/modify/reject) (1 hour)
4. Add "Accept All High Confidence" logic (30 min)
5. Update thumbnail display with metadata overlays (1 hour)
6. Testing (30 min)

---

## Phase 8: Rotation & Zoom Controls

**Estimated Time:** 3 hours
**Complexity:** Medium (UI controls, image manipulation)

### Objectives
Add comprehensive zoom controls and rotation functionality to ConvertImagesWindow Step 1.

### Key Features

#### Enhanced Zoom Controls
```python
class ZoomControls(QWidget):
    """Comprehensive zoom control widget"""
    zoom_changed = pyqtSignal(str, int)  # mode, value

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)

        # Zoom mode dropdown
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Fit to Width",
            "Fit to Height",
            "Fit to Window",
            "Custom %"
        ])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        layout.addWidget(QLabel("Zoom:"))
        layout.addWidget(self.mode_combo)

        # Percentage spinner (for Custom %)
        self.percent_spin = QSpinBox()
        self.percent_spin.setRange(25, 400)
        self.percent_spin.setSingleStep(25)
        self.percent_spin.setValue(100)
        self.percent_spin.setSuffix("%")
        self.percent_spin.valueChanged.connect(self._on_percent_changed)
        layout.addWidget(self.percent_spin)

        # Quick zoom buttons
        zoom_in = QPushButton("+")
        zoom_in.clicked.connect(lambda: self._adjust_zoom(25))
        layout.addWidget(zoom_in)

        zoom_out = QPushButton("-")
        zoom_out.clicked.connect(lambda: self._adjust_zoom(-25))
        layout.addWidget(zoom_out)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl++"), self, lambda: self._adjust_zoom(25))
        QShortcut(QKeySequence("Ctrl+-"), self, lambda: self._adjust_zoom(-25))
        QShortcut(QKeySequence("Ctrl+0"), self, self._reset_zoom)
```

#### Rotation Button Group
```python
class RotationControls(QWidget):
    """Rotation control buttons in 2x2 grid"""
    rotation_requested = pyqtSignal(int)  # degrees

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout(self)

        # 4 buttons in 2x2 grid
        btn_90ccw = QPushButton("⟲ 90°")
        btn_90ccw.clicked.connect(lambda: self.rotation_requested.emit(-90))
        layout.addWidget(btn_90ccw, 0, 0)

        btn_90cw = QPushButton("⟳ 90°")
        btn_90cw.clicked.connect(lambda: self.rotation_requested.emit(90))
        layout.addWidget(btn_90cw, 0, 1)

        btn_180 = QPushButton("↻ 180°")
        btn_180.clicked.connect(lambda: self.rotation_requested.emit(180))
        layout.addWidget(btn_180, 1, 0)

        btn_270 = QPushButton("⤾ 270°")
        btn_270.clicked.connect(lambda: self.rotation_requested.emit(270))
        layout.addWidget(btn_270, 1, 1)
```

#### Rotation Implementation
```python
def _rotate_current_page(self, degrees):
    """Rotate the currently selected page"""
    if not self.current_file:
        return

    # Load image
    from PIL import Image
    img = Image.open(self.current_file)

    # Rotate (PIL rotates counter-clockwise, negate for clockwise)
    if degrees == -90:
        img = img.rotate(90, expand=True)
    elif degrees == 90:
        img = img.rotate(-90, expand=True)
    elif degrees == 180:
        img = img.rotate(180, expand=True)
    elif degrees == 270:
        img = img.rotate(-270, expand=True)

    # Save (overwrite original)
    img.save(self.current_file)

    # Invalidate cache
    self.metadata_db.delete_metadata(self.current_file)

    # Save rotation preference
    self.analysis_db.save_rotation_preference(
        self.current_file,
        degrees,
        'manual'
    )

    # Refresh preview
    self._update_preview()
    self._update_thumbnail(self.current_file)
```

### Files to Modify
- `src/gui.py` (ConvertImagesWindow, add zoom and rotation controls)

### Implementation Steps
1. Create ZoomControls widget (1 hour)
2. Create RotationControls widget (30 min)
3. Implement zoom mode logic (fit to width/height/window) (1 hour)
4. Implement rotation with PIL (30 min)
5. Add visual indicators (rotation badges, needsrotation marker) (30 min)
6. Testing (30 min)

---

## Phase 9: UI Redesign - Visual Polish

**Estimated Time:** 2-3 hours
**Complexity:** Low-Medium (styling, CSS)

### Objectives
Apply modern visual design with consistent color palette, improved layouts, and micro-interactions.

### Create styles.py Module
```python
"""
Centralized stylesheet definitions
"""

# Color Palette
PRIMARY = "#2563EB"      # Modern Blue
SUCCESS = "#059669"      # Emerald
DANGER = "#DC2626"       # Red
WARNING = "#F59E0B"      # Amber
BG_LIGHT = "#F3F4F6"     # Light gray
BG_DARK = "#1F2937"      # Dark gray
TEXT_LIGHT = "#111827"   # Almost black
TEXT_DARK = "#F9FAFB"    # Off-white

# Button Styles
BUTTON_PRIMARY = f"""
QPushButton {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-size: 11pt;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: #1D4ED8;
    transform: translateY(-2px);
}}
QPushButton:pressed {{
    background-color: #1E40AF;
}}
QPushButton:disabled {{
    background-color: #9CA3AF;
    color: #D1D5DB;
}}
"""

BUTTON_SUCCESS = f"""
QPushButton {{
    background-color: {SUCCESS};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
}}
QPushButton:hover {{
    background-color: #047857;
}}
"""

BUTTON_DANGER = f"""
QPushButton {{
    background-color: {DANGER};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
}}
QPushButton:hover {{
    background-color: #B91C1C;
}}
"""

# Card Style
CARD_STYLE = """
QFrame {
    background-color: white;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 16px;
}
"""

# Apply to all windows
def apply_modern_theme(widget):
    """Apply modern theme to a widget"""
    widget.setStyleSheet("""
        QMainWindow, QDialog, QWidget {
            background-color: #F9FAFB;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10pt;
        }

        QLabel {
            color: #111827;
        }

        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: white;
            border: 1px solid #D1D5DB;
            border-radius: 4px;
            padding: 8px;
        }

        QLineEdit:focus, QTextEdit:focus {
            border-color: #2563EB;
        }
    """)
```

### Implementation Steps
1. Create `src/styles.py` (1 hour)
2. Update StartupWindow with new styles (30 min)
3. Update ConvertImagesWindow with card-based layout (1 hour)
4. Update Settings dialog with modern styling (30 min)
5. Add micro-interactions (hover effects, transitions) (30 min)
6. Testing on different screen sizes (30 min)

---

## Phase 10: Integration & Testing

**Estimated Time:** 3-4 hours
**Complexity:** Medium (end-to-end scenarios)

### Objectives
Comprehensive testing of all features working together.

### Test Scenarios

#### Scenario 1: Fresh Install Workflow
1. Launch application (no existing database)
2. Click "Change Settings" - verify defaults
3. Set scan folder
4. Click "Convert Scans" - verify empty state message
5. Add test images to scan folder
6. Re-launch "Convert Scans" - images appear

#### Scenario 2: PDF Extraction and Processing
1. Place PDF in scan folder
2. Click "Convert PDFs"
3. Extract pages
4. Close PDF window
5. Click "Convert Scans"
6. Verify extracted PNGs appear
7. Process through full workflow

#### Scenario 3: Provider Switching
1. Open Settings → LLM Provider tab
2. Switch from Ollama to Claude CLI
3. Verify model dropdown updates
4. Test prompt optimization (if CLI installed)
5. Switch back to Ollama
6. Verify settings persist after restart

#### Scenario 4: Bundle Suggestions
1. Have 10+ analyzed images
2. Click "Convert Scans"
3. Verify bundle suggestions appear (if applicable)
4. Accept a high-confidence bundle
5. Verify skips to next step with bundle

#### Scenario 5: Rotation and Zoom
1. Open "Convert Scans"
2. Select image in Step 1
3. Try all zoom modes (fit to width/height/window/custom)
4. Rotate image 90°
5. Verify PNG updated
6. Verify rotation persists

### Performance Testing
- [ ] Startup time < 2 seconds
- [ ] Image thumbnail generation < 500ms per image
- [ ] PDF extraction at 300 DPI: ~0.5-1s per page
- [ ] Database queries < 100ms
- [ ] No UI freezing during operations
- [ ] Memory usage reasonable (< 500MB for 100 images)

### Documentation Updates
1. Update README.md with new features
2. Create USER_GUIDE.md with screenshots
3. Document provider configuration
4. Add troubleshooting section
5. Update TESTING_SUMMARY.md with Phase 6-9 results

---

## Git Workflow for Remaining Phases

### Branch Strategy
```bash
# Continue on master or create feature branches
git checkout -b feature/phase-6-settings
# ... implement Phase 6 ...
git add src/gui.py src/config_manager.py
git commit -m "feat: Phase 6 - Enhanced Settings Window..."
git checkout master
git merge feature/phase-6-settings

# Repeat for each phase
```

### Commit After Each Phase
- Phase 6: `feat: Phase 6 - Enhanced Settings Window...`
- Phase 7: `feat: Phase 7 - Document Bundling UI...`
- Phase 8: `feat: Phase 8 - Rotation & Zoom Controls...`
- Phase 9: `feat: Phase 9 - UI Redesign and Polish...`
- Phase 10: `docs: Phase 10 - Documentation and Testing...`

---

## Estimated Timeline

| Phase | Hours | Days (4h/day) |
|-------|-------|---------------|
| Phase 6 | 4-5h | 1-1.5 days |
| Phase 7 | 3-4h | 1 day |
| Phase 8 | 3h | 0.75 days |
| Phase 9 | 2-3h | 0.5-0.75 days |
| Phase 10 | 3-4h | 1 day |
| **Total** | **15-19h** | **4-5 days** |

---

## Priority Recommendations

### Must-Have (Critical Path)
1. **Phase 6** - Settings window is essential for configuration
2. **Phase 8** - Rotation is needed for document processing
3. **Phase 10** - Testing ensures quality

### Nice-to-Have (Enhanced UX)
1. **Phase 7** - Bundle suggestions improve workflow but not required
2. **Phase 9** - Visual polish improves feel but not functional

### Suggested Order
1. Phase 6 (Settings) - Most important
2. Phase 8 (Rotation/Zoom) - Functional need
3. Phase 7 (Bundling UI) - Workflow enhancement
4. Phase 9 (Visual Polish) - UX improvement
5. Phase 10 (Testing) - Final validation

---

## Support Resources

### Code References
- **Existing SettingsWindow:** `src/gui.py` lines 147-656
- **ConvertImagesWindow:** `src/gui.py` lines 990-3900+
- **BundlingService:** `src/bundling_service.py`
- **ConfigManager:** `src/config_manager.py`

### Libraries Used
- **PyQt6** - UI framework
- **PyMuPDF (fitz)** - PDF operations
- **PIL/Pillow** - Image manipulation
- **sqlite3** - Database (built-in)

### Testing Tools
- **simple_test_runner.py** - Quick validation
- **run_all_tests.py** - Full test suite
- Manual testing via `python src/gui.py`

---

**Document Version:** 1.0
**Created:** 2026-02-02
**Status:** Planning guide for Phases 6-10
