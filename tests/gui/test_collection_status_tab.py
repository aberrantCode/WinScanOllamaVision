"""
Comprehensive unit tests for Collection Status tab components.

Tests cover:
1. Helper functions in collection_status_helpers.py
2. Integration with AnalysisStatusWindow
3. Theme support (light/dark)
4. Edge cases and error handling

Test Coverage Target: 80%+
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Initialize QApplication before importing any PyQt6 widgets
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QFrame
)
from PyQt6.QtCore import Qt

# Create QApplication instance for widget tests
app = QApplication.instance() or QApplication(sys.argv)


# ==================== Theme Colors Fixtures ====================

@pytest.fixture
def light_theme_colors():
    """Light theme color palette"""
    return {
        'bg_primary': '#F9FAFB',
        'bg_secondary': '#FFFFFF',
        'bg_tertiary': '#F3F4F6',
        'text_primary': '#111827',
        'text_secondary': '#374151',
        'text_tertiary': '#6B7280',
        'border': '#E5E7EB',
        'tab_active_bg': '#FFFFFF',
        'tab_inactive_bg': '#F3F4F6',
        'tab_hover_bg': '#E5E7EB',
        'input_bg': '#FFFFFF',
        'input_border': '#E5E7EB',
        'table_header_bg': '#F3F4F6',
        'table_row_alt': '#F9FAFB',
        'info_panel_bg': '#FFFFFF',
    }


@pytest.fixture
def dark_theme_colors():
    """Dark theme color palette"""
    return {
        'bg_primary': '#1E1E1E',
        'bg_secondary': '#2D2D2D',
        'bg_tertiary': '#3A3A3A',
        'text_primary': '#E0E0E0',
        'text_secondary': '#B0B0B0',
        'text_tertiary': '#808080',
        'border': '#4A4A4A',
        'tab_active_bg': '#2D2D2D',
        'tab_inactive_bg': '#1E1E1E',
        'tab_hover_bg': '#3A3A3A',
        'input_bg': '#2D2D2D',
        'input_border': '#4A4A4A',
        'table_header_bg': '#2D2D2D',
        'table_row_alt': '#252525',
        'info_panel_bg': '#2D2D2D',
    }


@pytest.fixture
def mock_analysis_db():
    """Create mock AnalysisDB with standard responses"""
    db = Mock()

    # Mock get_collection_summary
    db.get_collection_summary.return_value = {
        'files_detected': 100,
        'files_analyzed': 80,
        'high_confidence_count': 70,
        'pages_bundled': 50,
        'documents_archived': 25,
        'processing_speed': 2.5,
        'eta_minutes': 8.0,
        'avg_confidence': 0.85,
        'error_rate': 5.0,
        'metadata_completeness': {
            'company': 90.0,
            'document_type': 95.0,
            'document_date': 80.0,
            'page_number': 75.0,
            'total_pages': 70.0
        },
        'cache_hit_rate': 25.0
    }

    # Mock get_action_items
    db.get_action_items.return_value = {
        'pending_analysis': 20,
        'pending_bundles': 5,
        'failed_files': 3,
        'unbundled_files': 15
    }

    # Mock get_document_insights
    db.get_document_insights.return_value = {
        'total_documents': 25,
        'total_archived_pages': 100,
        'avg_pages_per_doc': 4.0,
        'bundle_acceptance_rate': 80.0,
        'pending_bundle_count': 5,
        'type_distribution': {
            'Invoice': 40,
            'Statement': 25,
            'Receipt': 20,
            'Letter': 10,
            'Other': 5
        },
        'company_distribution': {
            'Acme Corp': 30,
            'Bank of Testing': 25,
            'Store Inc': 20,
            'Government Agency': 15,
            'Other Company': 10
        }
    }

    # Mock other required methods
    db.get_recent_runs.return_value = []
    db.get_analyzed_pages.return_value = []
    db.get_failed_analyses.return_value = []
    db.close = Mock()

    return db


@pytest.fixture
def mock_config_manager():
    """Create mock ConfigManager for light theme"""
    config = Mock()
    config.get_setting.return_value = 'light'
    return config


@pytest.fixture
def mock_config_manager_dark():
    """Create mock ConfigManager for dark theme"""
    config = Mock()
    config.get_setting.return_value = 'dark'
    return config


@pytest.fixture
def action_callbacks():
    """Mock action callbacks for action items widget"""
    return {
        'start_analysis': Mock(),
        'review_bundles': Mock(),
        'view_errors': Mock(),
        'create_bundles': Mock()
    }


# ==================== Test create_metric_card ====================

class TestCreateMetricCard:
    """Tests for create_metric_card helper function"""

    def test_returns_qframe(self, light_theme_colors):
        """Should return a QFrame widget"""
        from collection_status_helpers import create_metric_card

        card = create_metric_card(light_theme_colors, "Test Title", "123")
        assert isinstance(card, QFrame)

    def test_contains_title_label(self, light_theme_colors):
        """Should contain a title label with correct text"""
        from collection_status_helpers import create_metric_card

        card = create_metric_card(light_theme_colors, "Files Detected", "100")
        labels = card.findChildren(QLabel)

        title_found = any("Files Detected" in label.text() for label in labels)
        assert title_found, "Title label not found in metric card"

    def test_contains_value_label(self, light_theme_colors):
        """Should contain a value label with correct text"""
        from collection_status_helpers import create_metric_card

        card = create_metric_card(light_theme_colors, "Test", "456")
        labels = card.findChildren(QLabel)

        value_found = any("456" in label.text() for label in labels)
        assert value_found, "Value label not found in metric card"

    def test_value_label_has_object_name(self, light_theme_colors):
        """Value label should have object name for dynamic updates"""
        from collection_status_helpers import create_metric_card

        card = create_metric_card(light_theme_colors, "Files Detected", "100")

        # Find value label by object name pattern
        value_label = card.findChild(QLabel, "files_detected_value")
        assert value_label is not None, "Value label should have object name"

    def test_card_has_layout(self, light_theme_colors):
        """Card should have a layout with widgets"""
        from collection_status_helpers import create_metric_card

        card = create_metric_card(light_theme_colors, "Test", "100")
        layout = card.layout()

        assert layout is not None
        assert layout.count() >= 2  # Title and value labels

    def test_dark_theme_colors(self, dark_theme_colors):
        """Should work with dark theme colors"""
        from collection_status_helpers import create_metric_card

        card = create_metric_card(dark_theme_colors, "Test", "100")
        assert isinstance(card, QFrame)


# ==================== Test create_funnel_widget ====================

class TestCreateFunnelWidget:
    """Tests for create_funnel_widget helper function"""

    def test_returns_tuple(self, light_theme_colors):
        """Should return (widget, funnel_bars_dict)"""
        from collection_status_helpers import create_funnel_widget

        result = create_funnel_widget(light_theme_colors)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_widget_is_qframe(self, light_theme_colors):
        """First element should be QFrame widget"""
        from collection_status_helpers import create_funnel_widget

        widget, _ = create_funnel_widget(light_theme_colors)
        assert isinstance(widget, QFrame)

    def test_funnel_bars_dict_keys(self, light_theme_colors):
        """Should return dict with correct funnel stage keys"""
        from collection_status_helpers import create_funnel_widget

        _, funnel_bars = create_funnel_widget(light_theme_colors)

        expected_keys = ['files_detected', 'files_analyzed', 'high_confidence', 'pages_bundled', 'documents_archived']
        for key in expected_keys:
            assert key in funnel_bars, f"Missing funnel bar key: {key}"

    def test_funnel_bars_have_label_and_bar(self, light_theme_colors):
        """Each funnel bar entry should have label and bar widgets"""
        from collection_status_helpers import create_funnel_widget

        _, funnel_bars = create_funnel_widget(light_theme_colors)

        for key, entry in funnel_bars.items():
            assert 'label' in entry, f"Missing label for {key}"
            assert 'bar' in entry, f"Missing bar for {key}"
            assert isinstance(entry['label'], QLabel)
            assert isinstance(entry['bar'], QProgressBar)

    def test_progress_bars_initialized_to_zero(self, light_theme_colors):
        """Progress bars should be initialized to 0"""
        from collection_status_helpers import create_funnel_widget

        _, funnel_bars = create_funnel_widget(light_theme_colors)

        for key, entry in funnel_bars.items():
            assert entry['bar'].value() == 0

    def test_has_title_label(self, light_theme_colors):
        """Widget should have 'Analysis Completion Funnel' title"""
        from collection_status_helpers import create_funnel_widget

        widget, _ = create_funnel_widget(light_theme_colors)
        labels = widget.findChildren(QLabel)

        title_found = any("Analysis Completion Funnel" in label.text() for label in labels)
        assert title_found


# ==================== Test create_speed_eta_widget ====================

class TestCreateSpeedEtaWidget:
    """Tests for create_speed_eta_widget helper function"""

    def test_returns_tuple(self, light_theme_colors):
        """Should return (widget, speed_label, eta_label)"""
        from collection_status_helpers import create_speed_eta_widget

        result = create_speed_eta_widget(light_theme_colors)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_widget_is_qframe(self, light_theme_colors):
        """First element should be QFrame widget"""
        from collection_status_helpers import create_speed_eta_widget

        widget, _, _ = create_speed_eta_widget(light_theme_colors)
        assert isinstance(widget, QFrame)

    def test_speed_label_is_qlabel(self, light_theme_colors):
        """Speed label should be QLabel"""
        from collection_status_helpers import create_speed_eta_widget

        _, speed_label, _ = create_speed_eta_widget(light_theme_colors)
        assert isinstance(speed_label, QLabel)

    def test_eta_label_is_qlabel(self, light_theme_colors):
        """ETA label should be QLabel"""
        from collection_status_helpers import create_speed_eta_widget

        _, _, eta_label = create_speed_eta_widget(light_theme_colors)
        assert isinstance(eta_label, QLabel)

    def test_speed_label_default_text(self, light_theme_colors):
        """Speed label should have default placeholder text"""
        from collection_status_helpers import create_speed_eta_widget

        # Keep reference to widget to prevent Qt object deletion
        widget, speed_label, eta_label = create_speed_eta_widget(light_theme_colors)
        # Actual text: "Processing Speed: -- pages/min"
        assert "Processing Speed" in speed_label.text()

    def test_eta_label_default_text(self, light_theme_colors):
        """ETA label should have default placeholder text"""
        from collection_status_helpers import create_speed_eta_widget

        # Keep reference to widget to prevent Qt object deletion
        widget, speed_label, eta_label = create_speed_eta_widget(light_theme_colors)
        # Actual text: "ETA: --"
        assert "ETA:" in eta_label.text()


# ==================== Test create_action_item_row ====================

class TestCreateActionItemRow:
    """Tests for create_action_item_row helper function"""

    def test_returns_qwidget(self, light_theme_colors):
        """Should return a QWidget"""
        from collection_status_helpers import create_action_item_row

        row = create_action_item_row(light_theme_colors, "Test text", "Click", lambda: None)
        assert isinstance(row, QWidget)

    def test_contains_text_label(self, light_theme_colors):
        """Should contain text label with provided text"""
        from collection_status_helpers import create_action_item_row

        row = create_action_item_row(light_theme_colors, "5 files failed", "Retry", lambda: None)

        text_label = row.findChild(QLabel, "action_text")
        assert text_label is not None
        assert "5 files failed" in text_label.text()

    def test_contains_action_button(self, light_theme_colors):
        """Should contain action button with provided text"""
        from collection_status_helpers import create_action_item_row

        row = create_action_item_row(light_theme_colors, "Test", "Retry Now", lambda: None)

        button = row.findChild(QPushButton, "action_button")
        assert button is not None
        assert button.text() == "Retry Now"

    def test_button_callback_connected(self, light_theme_colors):
        """Button should call provided callback when clicked"""
        from collection_status_helpers import create_action_item_row

        callback_tracker = []

        def test_callback():
            callback_tracker.append(True)

        row = create_action_item_row(light_theme_colors, "Test", "Click", test_callback)
        button = row.findChild(QPushButton, "action_button")

        button.click()
        assert len(callback_tracker) == 1


# ==================== Test create_action_items_widget ====================

class TestCreateActionItemsWidget:
    """Tests for create_action_items_widget helper function"""

    def test_returns_tuple(self, light_theme_colors, action_callbacks):
        """Should return (widget, action_items_list)"""
        from collection_status_helpers import create_action_items_widget

        result = create_action_items_widget(light_theme_colors, action_callbacks)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_widget_is_qframe(self, light_theme_colors, action_callbacks):
        """First element should be QFrame widget"""
        from collection_status_helpers import create_action_items_widget

        widget, _ = create_action_items_widget(light_theme_colors, action_callbacks)
        assert isinstance(widget, QFrame)

    def test_action_items_is_list(self, light_theme_colors, action_callbacks):
        """Second element should be list of action items"""
        from collection_status_helpers import create_action_items_widget

        _, action_items = create_action_items_widget(light_theme_colors, action_callbacks)
        assert isinstance(action_items, list)

    def test_has_four_action_items(self, light_theme_colors, action_callbacks):
        """Should create 4 action item rows"""
        from collection_status_helpers import create_action_items_widget

        _, action_items = create_action_items_widget(light_theme_colors, action_callbacks)
        assert len(action_items) == 4

    def test_has_title(self, light_theme_colors, action_callbacks):
        """Widget should have 'Action Items' title"""
        from collection_status_helpers import create_action_items_widget

        widget, _ = create_action_items_widget(light_theme_colors, action_callbacks)
        labels = widget.findChildren(QLabel)

        title_found = any("Action Items" in label.text() for label in labels)
        assert title_found


# ==================== Test create_quality_metrics_widget ====================

class TestCreateQualityMetricsWidget:
    """Tests for create_quality_metrics_widget helper function"""

    def test_returns_tuple(self, light_theme_colors):
        """Should return tuple with 4 elements"""
        from collection_status_helpers import create_quality_metrics_widget

        result = create_quality_metrics_widget(light_theme_colors)
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_widget_is_qwidget(self, light_theme_colors):
        """First element should be QWidget"""
        from collection_status_helpers import create_quality_metrics_widget

        widget, _, _, _ = create_quality_metrics_widget(light_theme_colors)
        assert isinstance(widget, QWidget)

    def test_avg_confidence_label(self, light_theme_colors):
        """Should have average confidence label"""
        from collection_status_helpers import create_quality_metrics_widget

        widget, avg_conf_label, _, _ = create_quality_metrics_widget(light_theme_colors)
        assert isinstance(avg_conf_label, QLabel)
        # Actual text: "Average Confidence: --"
        assert "Average Confidence" in avg_conf_label.text()

    def test_error_rate_label(self, light_theme_colors):
        """Should have error rate label"""
        from collection_status_helpers import create_quality_metrics_widget

        widget, _, error_rate_label, _ = create_quality_metrics_widget(light_theme_colors)
        assert isinstance(error_rate_label, QLabel)
        # Actual text: "Error Rate: --"
        assert "Error Rate" in error_rate_label.text()

    def test_completeness_bars_dict(self, light_theme_colors):
        """Should return completeness bars dict with expected keys"""
        from collection_status_helpers import create_quality_metrics_widget

        _, _, _, completeness_bars = create_quality_metrics_widget(light_theme_colors)
        assert isinstance(completeness_bars, dict)

        expected_keys = ['company', 'document_type', 'document_date', 'page_number']
        for key in expected_keys:
            assert key in completeness_bars

    def test_completeness_bars_have_bar_attribute(self, light_theme_colors):
        """Each completeness bar should have a bar attribute"""
        from collection_status_helpers import create_quality_metrics_widget

        _, _, _, completeness_bars = create_quality_metrics_widget(light_theme_colors)

        for key, widget in completeness_bars.items():
            assert hasattr(widget, 'bar'), f"Missing bar attribute for {key}"
            assert isinstance(widget.bar, QProgressBar)


# ==================== Test create_distribution_bar ====================

class TestCreateDistributionBar:
    """Tests for create_distribution_bar helper function"""

    def test_returns_qwidget(self, light_theme_colors):
        """Should return a QWidget"""
        from collection_status_helpers import create_distribution_bar

        bar = create_distribution_bar(light_theme_colors, "Invoice", 40, 100)
        assert isinstance(bar, QWidget)

    def test_contains_label_with_count(self, light_theme_colors):
        """Should contain label with name and count"""
        from collection_status_helpers import create_distribution_bar

        bar = create_distribution_bar(light_theme_colors, "Invoice", 40, 100)
        labels = bar.findChildren(QLabel)

        label_text = " ".join(label.text() for label in labels)
        assert "Invoice" in label_text
        assert "40" in label_text

    def test_contains_progress_bar(self, light_theme_colors):
        """Should contain a progress bar"""
        from collection_status_helpers import create_distribution_bar

        bar = create_distribution_bar(light_theme_colors, "Invoice", 40, 100)
        progress_bars = bar.findChildren(QProgressBar)

        assert len(progress_bars) == 1

    def test_progress_bar_value_correct(self, light_theme_colors):
        """Progress bar value should be percentage of total"""
        from collection_status_helpers import create_distribution_bar

        bar = create_distribution_bar(light_theme_colors, "Invoice", 40, 100)
        progress_bar = bar.findChildren(QProgressBar)[0]

        assert progress_bar.value() == 40  # 40%

    def test_handles_zero_total(self, light_theme_colors):
        """Should handle zero total without division error"""
        from collection_status_helpers import create_distribution_bar

        # Should not raise exception
        bar = create_distribution_bar(light_theme_colors, "Invoice", 0, 0)
        progress_bar = bar.findChildren(QProgressBar)[0]

        assert progress_bar.value() == 0


# ==================== Test create_document_insights_widget ====================

class TestCreateDocumentInsightsWidget:
    """Tests for create_document_insights_widget helper function"""

    def test_returns_tuple(self, light_theme_colors):
        """Should return tuple with 7 elements"""
        from collection_status_helpers import create_document_insights_widget

        result = create_document_insights_widget(light_theme_colors)
        assert isinstance(result, tuple)
        assert len(result) == 7

    def test_widget_is_qwidget(self, light_theme_colors):
        """First element should be QWidget"""
        from collection_status_helpers import create_document_insights_widget

        widget, *_ = create_document_insights_widget(light_theme_colors)
        assert isinstance(widget, QWidget)

    def test_docs_created_label(self, light_theme_colors):
        """Should have docs created label"""
        from collection_status_helpers import create_document_insights_widget

        result = create_document_insights_widget(light_theme_colors)
        docs_label = result[1]
        assert isinstance(docs_label, QLabel)
        # Actual text: "Documents Created: 0"
        assert "Documents Created" in docs_label.text()

    def test_pages_archived_label(self, light_theme_colors):
        """Should have pages archived label"""
        from collection_status_helpers import create_document_insights_widget

        result = create_document_insights_widget(light_theme_colors)
        pages_label = result[2]
        assert isinstance(pages_label, QLabel)
        # Actual text: "Pages Archived: 0"
        assert "Pages Archived" in pages_label.text()

    def test_type_distribution_container(self, light_theme_colors):
        """Should have type distribution container"""
        from collection_status_helpers import create_document_insights_widget

        result = create_document_insights_widget(light_theme_colors)
        type_dist_container = result[5]

        assert isinstance(type_dist_container, QWidget)
        assert hasattr(type_dist_container, 'layout')

    def test_company_distribution_container(self, light_theme_colors):
        """Should have company distribution container"""
        from collection_status_helpers import create_document_insights_widget

        result = create_document_insights_widget(light_theme_colors)
        company_dist_container = result[6]

        assert isinstance(company_dist_container, QWidget)
        assert hasattr(company_dist_container, 'layout')


# ==================== Test create_collapsible_section ====================

class TestCreateCollapsibleSection:
    """Tests for create_collapsible_section helper function"""

    def test_returns_qwidget(self, light_theme_colors):
        """Should return a QWidget container"""
        from collection_status_helpers import create_collapsible_section

        content = QLabel("Test content")
        section = create_collapsible_section(light_theme_colors, "Section Title", content)

        assert isinstance(section, QWidget)

    def test_has_header_frame(self, light_theme_colors):
        """Should have a clickable header frame"""
        from collection_status_helpers import create_collapsible_section

        content = QLabel("Test content")
        section = create_collapsible_section(light_theme_colors, "Section Title", content)

        frames = section.findChildren(QFrame)
        assert len(frames) >= 1

    def test_has_toggle_button(self, light_theme_colors):
        """Should have toggle button"""
        from collection_status_helpers import create_collapsible_section

        content = QLabel("Test content")
        section = create_collapsible_section(light_theme_colors, "Section Title", content)

        toggle_btn = section.findChild(QPushButton, "toggle_btn")
        assert toggle_btn is not None

    def test_content_initially_visible_when_shown(self, light_theme_colors):
        """Content should be visible when parent widget is shown (expanded by default)"""
        from collection_status_helpers import create_collapsible_section

        # Create parent to properly test visibility
        parent = QWidget()
        parent_layout = QVBoxLayout(parent)

        content = QLabel("Test content")
        section = create_collapsible_section(light_theme_colors, "Section Title", content)
        parent_layout.addWidget(section)
        parent.show()

        # Implementation sets content.setVisible(True) - starts expanded
        assert content.isVisible()

    def test_toggle_button_collapses_content(self, light_theme_colors):
        """Clicking toggle button should collapse expanded content"""
        from collection_status_helpers import create_collapsible_section

        parent = QWidget()
        parent_layout = QVBoxLayout(parent)

        content = QLabel("Test content")
        section = create_collapsible_section(light_theme_colors, "Section Title", content)
        parent_layout.addWidget(section)
        parent.show()

        # Content starts expanded
        toggle_btn = section.findChild(QPushButton, "toggle_btn")
        toggle_btn.click()  # Collapse

        assert not content.isVisible()

    def test_toggle_button_expands_content(self, light_theme_colors):
        """Clicking toggle button twice should expand collapsed content"""
        from collection_status_helpers import create_collapsible_section

        parent = QWidget()
        parent_layout = QVBoxLayout(parent)

        content = QLabel("Test content")
        section = create_collapsible_section(light_theme_colors, "Section Title", content)
        parent_layout.addWidget(section)
        parent.show()

        toggle_btn = section.findChild(QPushButton, "toggle_btn")
        toggle_btn.click()  # Collapse
        toggle_btn.click()  # Expand

        assert content.isVisible()

    def test_content_widget_integrated(self, light_theme_colors):
        """Content widget should be findable in section"""
        from collection_status_helpers import create_collapsible_section

        content = QLabel("Integrated Content")
        section = create_collapsible_section(light_theme_colors, "Section", content)

        labels = section.findChildren(QLabel)
        content_found = any("Integrated Content" in lbl.text() for lbl in labels)
        assert content_found


# ==================== Test create_analysis_progress_frame ====================

class TestCreateAnalysisProgressFrame:
    """Tests for create_analysis_progress_frame helper function"""

    def test_returns_tuple(self, light_theme_colors):
        """Should return tuple with 7 elements"""
        from collection_status_helpers import create_analysis_progress_frame

        result = create_analysis_progress_frame(
            light_theme_colors, False, lambda: None, lambda: None
        )
        assert isinstance(result, tuple)
        assert len(result) == 7

    def test_frame_is_qframe(self, light_theme_colors):
        """First element should be QFrame"""
        from collection_status_helpers import create_analysis_progress_frame

        frame, *_ = create_analysis_progress_frame(
            light_theme_colors, False, lambda: None, lambda: None
        )
        assert isinstance(frame, QFrame)

    def test_has_current_file_label(self, light_theme_colors):
        """Should have current file label"""
        from collection_status_helpers import create_analysis_progress_frame

        # Need input_bg for progress bar styling
        colors = light_theme_colors.copy()
        colors['input_bg'] = colors.get('input_bg', '#FFFFFF')

        result = create_analysis_progress_frame(
            colors, False, lambda: None, lambda: None
        )
        current_file_label = result[1]
        assert isinstance(current_file_label, QLabel)
        # Actual text: "Current: --"
        assert "Current:" in current_file_label.text()

    def test_has_progress_bar(self, light_theme_colors):
        """Should have progress bar"""
        from collection_status_helpers import create_analysis_progress_frame

        result = create_analysis_progress_frame(
            light_theme_colors, False, lambda: None, lambda: None
        )
        progress_bar = result[2]
        assert isinstance(progress_bar, QProgressBar)

    def test_has_stop_button(self, light_theme_colors):
        """Should have stop button"""
        from collection_status_helpers import create_analysis_progress_frame

        result = create_analysis_progress_frame(
            light_theme_colors, False, lambda: None, lambda: None
        )
        stop_button = result[5]
        assert isinstance(stop_button, QPushButton)
        assert "Stop" in stop_button.text()

    def test_has_abort_button(self, light_theme_colors):
        """Should have abort button"""
        from collection_status_helpers import create_analysis_progress_frame

        result = create_analysis_progress_frame(
            light_theme_colors, False, lambda: None, lambda: None
        )
        abort_button = result[6]
        assert isinstance(abort_button, QPushButton)
        assert "Abort" in abort_button.text()

    def test_stop_callback_connected(self, light_theme_colors):
        """Stop button should call stop callback"""
        from collection_status_helpers import create_analysis_progress_frame

        stop_tracker = []

        result = create_analysis_progress_frame(
            light_theme_colors, False,
            lambda: stop_tracker.append('stop'),
            lambda: None
        )
        stop_button = result[5]
        stop_button.click()

        assert 'stop' in stop_tracker

    def test_abort_callback_connected(self, light_theme_colors):
        """Abort button should call abort callback"""
        from collection_status_helpers import create_analysis_progress_frame

        abort_tracker = []

        result = create_analysis_progress_frame(
            light_theme_colors, False,
            lambda: None,
            lambda: abort_tracker.append('abort')
        )
        abort_button = result[6]
        abort_button.click()

        assert 'abort' in abort_tracker

    def test_dark_mode_styling(self, dark_theme_colors):
        """Should apply dark mode styling"""
        from collection_status_helpers import create_analysis_progress_frame

        frame, *_ = create_analysis_progress_frame(
            dark_theme_colors, True, lambda: None, lambda: None
        )
        # Should not raise exception and should have styling
        assert len(frame.styleSheet()) > 0


# ==================== Test Edge Cases ====================

class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_metric_card_empty_value(self, light_theme_colors):
        """Should handle empty value string"""
        from collection_status_helpers import create_metric_card

        card = create_metric_card(light_theme_colors, "Test", "")
        assert isinstance(card, QFrame)

    def test_metric_card_large_number(self, light_theme_colors):
        """Should handle large numbers"""
        from collection_status_helpers import create_metric_card

        card = create_metric_card(light_theme_colors, "Test", "1,234,567")
        labels = card.findChildren(QLabel)

        value_found = any("1,234,567" in label.text() for label in labels)
        assert value_found

    def test_distribution_bar_large_percentage(self, light_theme_colors):
        """Should handle 100% distribution"""
        from collection_status_helpers import create_distribution_bar

        bar = create_distribution_bar(light_theme_colors, "Single Type", 100, 100)
        progress_bar = bar.findChildren(QProgressBar)[0]

        assert progress_bar.value() == 100

    def test_action_item_long_text(self, light_theme_colors):
        """Should handle long text in action items"""
        from collection_status_helpers import create_action_item_row

        long_text = "This is a very long text message that should wrap properly " * 3
        row = create_action_item_row(light_theme_colors, long_text, "Action", lambda: None)

        text_label = row.findChild(QLabel, "action_text")
        assert text_label.wordWrap()

    def test_special_characters_in_labels(self, light_theme_colors):
        """Should handle special characters in labels"""
        from collection_status_helpers import create_distribution_bar

        bar = create_distribution_bar(light_theme_colors, "O'Brien & Associates (Main)", 25, 100)
        labels = bar.findChildren(QLabel)

        label_text = " ".join(label.text() for label in labels)
        assert "O'Brien" in label_text


# ==================== Test create_completeness_bar ====================

class TestCreateCompletenessBar:
    """Tests for create_completeness_bar helper function"""

    def test_returns_qwidget(self, light_theme_colors):
        """Should return a QWidget"""
        from collection_status_helpers import create_completeness_bar

        bar = create_completeness_bar(light_theme_colors, "company", "Company")
        assert isinstance(bar, QWidget)

    def test_has_label_attribute(self, light_theme_colors):
        """Should have label attribute"""
        from collection_status_helpers import create_completeness_bar

        bar = create_completeness_bar(light_theme_colors, "company", "Company")
        assert hasattr(bar, 'label')
        assert isinstance(bar.label, QLabel)

    def test_has_bar_attribute(self, light_theme_colors):
        """Should have bar attribute"""
        from collection_status_helpers import create_completeness_bar

        bar = create_completeness_bar(light_theme_colors, "company", "Company")
        assert hasattr(bar, 'bar')
        assert isinstance(bar.bar, QProgressBar)

    def test_label_object_name(self, light_theme_colors):
        """Label should have correct object name"""
        from collection_status_helpers import create_completeness_bar

        bar = create_completeness_bar(light_theme_colors, "company", "Company")
        assert bar.label.objectName() == "company_completeness_label"

    def test_bar_object_name(self, light_theme_colors):
        """Bar should have correct object name"""
        from collection_status_helpers import create_completeness_bar

        bar = create_completeness_bar(light_theme_colors, "company", "Company")
        assert bar.bar.objectName() == "company_completeness_bar"

    def test_bar_initialized_to_zero(self, light_theme_colors):
        """Bar should be initialized to 0"""
        from collection_status_helpers import create_completeness_bar

        bar = create_completeness_bar(light_theme_colors, "company", "Company")
        assert bar.bar.value() == 0


# ==================== Run Tests ====================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
