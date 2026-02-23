# mypy: disable-error-code=attr-defined
"""Prompts tab mixin for EnhancedSettingsWindow."""

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.prompts import DEFAULT_ANALYSIS_PROMPT
from ui.settings_workers import ExpandablePromptEdit


class _SettingsTabPromptsMixin:
    """Mixin providing the Prompts configuration tab."""

    def _create_prompts_tab(self) -> QWidget:
        """Create the Prompts configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Prompts Group
        prompts_group = QGroupBox("Prompts Configuration")
        prompts_layout = QVBoxLayout(prompts_group)

        # Document Pages Prompt
        doc_validation_label = QLabel("Document Validation Prompt:")
        doc_validation_label.setToolTip(
            "Prompt used to validate if multiple pages belong to the same document.\n\n"
            "Purpose: When multiple pages are found, this prompt asks the LLM to\n"
            "determine which pages belong together as a single document.\n\n"
            "Implementation: Sent to the LLM with multiple page images.\n"
            "The LLM returns JSON indicating which pages belong together.\n\n"
            "Used by: Document bundling logic during analysis."
        )
        prompts_layout.addWidget(doc_validation_label)
        self.pages_prompt_edit = ExpandablePromptEdit()
        self.pages_prompt_edit.setToolTip(
            "This prompt analyzes multiple document page images to determine\n"
            "if they belong to the same physical document.\n\n"
            "The LLM uses visual cues like:\n"
            "• Consistent formatting and layout\n"
            "• Sequential page numbers\n"
            "• Continuation of content\n"
            "• Matching headers/footers\n\n"
            "Response format must be JSON with 'all_belong', 'doc_page_count',\n"
            "and 'do_not_belong' fields."
        )
        pages_prompt_default = """You are an expert document analyst. Examine the provided images and determine which pages belong to the same continuous physical document.

The first image should ALWAYS be considered as belonging to the document (it's the anchor page). Analyze each subsequent page to determine if it belongs with the first page or not.

Respond ONLY with valid JSON in this format:
{
  "all_belong": boolean,
  "doc_page_count": integer,
  "do_not_belong": [array of integers]
}

Where:
- **all_belong**: true if all provided pages belong together, false if any page doesn't belong
- **doc_page_count**: number of pages that belong together (including the first page)
- **do_not_belong**: array of page indices (1-based) that don't belong. The first page (index 1) should NEVER be in this array.

Examples:

If all 3 pages belong together:
{ "all_belong": true, "doc_page_count": 3, "do_not_belong": [] }

If 3 pages provided and page 2 doesn't belong:
{ "all_belong": false, "doc_page_count": 2, "do_not_belong": [2] }

If 5 pages provided and pages 3 and 5 don't belong:
{ "all_belong": false, "doc_page_count": 3, "do_not_belong": [3, 5] }"""
        pages_prompt = self.config_manager.get_setting(
            "Prompts", "document_pages", pages_prompt_default
        )
        self.pages_prompt_edit.setPlainText(pages_prompt)
        prompts_layout.addWidget(self.pages_prompt_edit)

        pages_buttons = QHBoxLayout()
        optimize_pages_btn = QPushButton("Optimize Prompt")
        optimize_pages_btn.clicked.connect(lambda: self._optimize_prompt(self.pages_prompt_edit))
        optimize_pages_btn.setObjectName("compactButton")
        reset_pages_btn = QPushButton("Reset to Default")
        reset_pages_btn.clicked.connect(
            lambda: self.pages_prompt_edit.setPlainText(pages_prompt_default)
        )
        reset_pages_btn.setObjectName("compactButton")
        pages_buttons.addWidget(optimize_pages_btn)
        pages_buttons.addWidget(reset_pages_btn)
        pages_buttons.addStretch()
        prompts_layout.addLayout(pages_buttons)

        # Document Metadata Prompt
        metadata_label = QLabel("Metadata Extraction Prompt:")
        metadata_label.setToolTip(
            "Prompt used to extract metadata from document images.\n\n"
            "Purpose: Analyzes each document page to extract structured information\n"
            "like company name, document type, date, page numbers, etc.\n\n"
            "Implementation: Sent to the LLM with one or more page images.\n"
            "The LLM returns JSON with all extracted metadata fields.\n\n"
            "Used by: Analysis service for every document page analyzed."
        )
        prompts_layout.addWidget(metadata_label)
        self.metadata_prompt_edit = ExpandablePromptEdit()
        self.metadata_prompt_edit.setToolTip(
            "This prompt extracts comprehensive metadata from document images.\n\n"
            "Extracted fields include:\n"
            "• company - Organization name\n"
            "• document_type - Invoice, Statement, Receipt, etc.\n"
            "• document_date - Primary date in YYYY-MM-DD format\n"
            "• tax_related - Boolean for tax-related documents\n"
            "• page_number/total_pages - Page information\n"
            "• rotation_needed - If image needs rotation\n"
            "• confidence_score - LLM's confidence (0.0-1.0)\n\n"
            "Response format must be valid JSON with all fields."
        )
        # Use the single source of truth from prompts module
        metadata_prompt = self.config_manager.get_setting(
            "Prompts", "document_metadata", DEFAULT_ANALYSIS_PROMPT
        )
        self.metadata_prompt_edit.setPlainText(metadata_prompt)
        prompts_layout.addWidget(self.metadata_prompt_edit)

        metadata_buttons = QHBoxLayout()
        optimize_metadata_btn = QPushButton("Optimize Prompt")
        optimize_metadata_btn.clicked.connect(
            lambda: self._optimize_prompt(self.metadata_prompt_edit)
        )
        optimize_metadata_btn.setObjectName("compactButton")
        reset_metadata_btn = QPushButton("Reset to Default")
        reset_metadata_btn.clicked.connect(
            lambda: self.metadata_prompt_edit.setPlainText(DEFAULT_ANALYSIS_PROMPT)
        )
        reset_metadata_btn.setObjectName("compactButton")
        metadata_buttons.addWidget(optimize_metadata_btn)
        metadata_buttons.addWidget(reset_metadata_btn)
        metadata_buttons.addStretch()
        prompts_layout.addLayout(metadata_buttons)

        layout.addWidget(prompts_group)

        layout.addStretch()

        return tab
