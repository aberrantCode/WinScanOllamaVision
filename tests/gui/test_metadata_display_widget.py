"""
Test MetadataDisplayWidget functionality
"""
import sys
import os
import pytest
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gui import MetadataDisplayWidget
from analysis_db import AnalysisDB


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def mock_analysis_db():
    """Create mock AnalysisDB"""
    db = Mock(spec=AnalysisDB)
    return db


@pytest.fixture
def widget(qapp, mock_analysis_db):
    """Create MetadataDisplayWidget instance"""
    widget = MetadataDisplayWidget(analysis_db=mock_analysis_db)
    return widget


def test_widget_initialization(widget):
    """Test that widget initializes correctly"""
    assert widget is not None
    assert widget.current_file_path is None
    assert widget.current_bundle_files == []
    assert hasattr(widget, 'analysis_card')
    assert hasattr(widget, 'bundle_card')
    assert hasattr(widget, 'confidence_badge')
    assert hasattr(widget, 'doc_type_label')
    assert hasattr(widget, 'company_label')
    assert hasattr(widget, 'date_label')
    assert hasattr(widget, 'page_label')
    assert hasattr(widget, 'rotation_label')
    assert hasattr(widget, 'bundle_count_label')


def test_set_current_file_no_analysis(widget, mock_analysis_db):
    """Test setting current file with no analysis data"""
    mock_analysis_db.get_analysis.return_value = None

    widget.set_current_file("test_file.png")

    assert widget.current_file_path == "test_file.png"
    assert "No Analysis Data" in widget.confidence_badge.text()
    assert "Document Type: --" == widget.doc_type_label.text()
    assert "Company: --" == widget.company_label.text()
    assert "Date: --" == widget.date_label.text()
    assert "Page: --" == widget.page_label.text()


def test_set_current_file_high_confidence(widget, mock_analysis_db):
    """Test setting current file with high confidence analysis"""
    analysis_data = {
        'confidence_score': 0.92,
        'document_type': 'Invoice',
        'company': 'Acme Corporation',
        'document_date': '2024-01-15',
        'page_number': 1,
        'total_pages': 6,
        'rotation_needed': False,
        'suggested_rotation': 0
    }
    mock_analysis_db.get_analysis.return_value = analysis_data

    widget.set_current_file("test_file.png")

    assert widget.current_file_path == "test_file.png"
    assert "HIGH CONFIDENCE" in widget.confidence_badge.text()
    assert "(92%)" in widget.confidence_badge.text()
    assert "🟢" in widget.confidence_badge.text()
    assert "Document Type: Invoice" == widget.doc_type_label.text()
    assert "Company: Acme Corporation" == widget.company_label.text()
    assert "Date: 2024-01-15" == widget.date_label.text()
    assert "Page: 1 of 6" == widget.page_label.text()
    assert "None needed ✓" in widget.rotation_label.text()


def test_set_current_file_medium_confidence(widget, mock_analysis_db):
    """Test setting current file with medium confidence analysis"""
    analysis_data = {
        'confidence_score': 0.65,
        'document_type': 'Statement',
        'company': 'Beta Inc',
        'document_date': '2024-01-12',
        'page_number': 2,
        'total_pages': 3,
        'rotation_needed': False
    }
    mock_analysis_db.get_analysis.return_value = analysis_data

    widget.set_current_file("test_file.png")

    assert "MEDIUM CONFIDENCE" in widget.confidence_badge.text()
    assert "(65%)" in widget.confidence_badge.text()
    assert "🟡" in widget.confidence_badge.text()


def test_set_current_file_low_confidence(widget, mock_analysis_db):
    """Test setting current file with low confidence analysis"""
    analysis_data = {
        'confidence_score': 0.35,
        'document_type': 'Receipt',
        'company': 'Charlie Co'
    }
    mock_analysis_db.get_analysis.return_value = analysis_data

    widget.set_current_file("test_file.png")

    assert "LOW CONFIDENCE" in widget.confidence_badge.text()
    assert "(35%)" in widget.confidence_badge.text()
    assert "🔴" in widget.confidence_badge.text()


def test_set_current_file_rotation_needed(widget, mock_analysis_db):
    """Test displaying rotation information when rotation is needed"""
    analysis_data = {
        'confidence_score': 0.88,
        'document_type': 'Invoice',
        'rotation_needed': True,
        'suggested_rotation': 90
    }
    mock_analysis_db.get_analysis.return_value = analysis_data

    widget.set_current_file("test_file.png")

    assert "90° suggested" in widget.rotation_label.text()


def test_set_bundle_files_empty(widget):
    """Test setting bundle files with empty list"""
    widget.set_bundle_files([])

    assert widget.current_bundle_files == []
    assert "0 pages included" in widget.bundle_count_label.text()


def test_set_bundle_files_single(widget):
    """Test setting bundle files with single file"""
    widget.set_bundle_files(["file1.png"])

    assert widget.current_bundle_files == ["file1.png"]
    assert "1 page included" in widget.bundle_count_label.text()


def test_set_bundle_files_multiple(widget):
    """Test setting bundle files with multiple files"""
    files = ["file1.png", "file2.png", "file3.png"]
    widget.set_bundle_files(files)

    assert widget.current_bundle_files == files
    assert "3 pages included" in widget.bundle_count_label.text()


def test_reanalyze_signal(widget, qapp):
    """Test that re-analyze button emits signal"""
    signal_received = []
    widget.re_analyze_requested.connect(lambda path: signal_received.append(path))

    widget.current_file_path = "test_file.png"
    widget.reanalyze_button.click()

    qapp.processEvents()
    assert len(signal_received) == 1
    assert signal_received[0] == "test_file.png"


def test_thumbnail_clicked_signal(widget, qapp, mock_analysis_db):
    """Test that clicking bundle thumbnail emits signal"""
    # Mock file existence for thumbnail creation
    with patch('os.path.basename', return_value="file1.png"):
        signal_received = []
        widget.thumbnail_clicked.connect(lambda path: signal_received.append(path))

        # Set bundle files to create thumbnails
        widget.set_bundle_files(["file1.png"])
        qapp.processEvents()

        # Find the thumbnail widget and simulate click
        thumbnail_container = widget.bundle_thumbnails_container
        for i in range(thumbnail_container.layout().count()):
            item = thumbnail_container.layout().itemAt(i)
            if item.widget() and hasattr(item.widget(), 'mousePressEvent'):
                # Simulate click by calling the mousePressEvent directly
                # Create a simple mock event
                from PyQt6.QtCore import QEvent, QPointF
                from PyQt6.QtGui import QMouseEvent
                event = QMouseEvent(
                    QEvent.Type.MouseButtonPress,
                    QPointF(item.widget().rect().center()),
                    Qt.MouseButton.LeftButton,
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier
                )
                item.widget().mousePressEvent(event)
                qapp.processEvents()
                break

        # Check signal was emitted
        assert len(signal_received) == 1
        assert signal_received[0] == "file1.png"


def test_show_no_analysis(widget):
    """Test _show_no_analysis method"""
    widget._show_no_analysis()

    assert "No Analysis Data" in widget.confidence_badge.text()
    assert "Document Type: --" == widget.doc_type_label.text()
    assert "Company: --" == widget.company_label.text()
    assert "Date: --" == widget.date_label.text()
    assert "Page: --" == widget.page_label.text()
    assert "Rotation: --" == widget.rotation_label.text()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
