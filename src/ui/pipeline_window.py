"""
Backward-compatibility shim.

All implementations have moved to the ui.pipeline subpackage.
This module re-exports the full public API so existing imports continue to work.
"""

from ui.pipeline import (  # noqa: F401
    _LINK_STYLE,
    STAGE_ANALYZE,
    STAGE_BUNDLE,
    STAGE_EXPORT,
    STAGE_IMPORT,
    STAGE_LABELS,
    AnalyzePanel,
    BundlePanel,
    DocumentPipelineWindow,
    ExportPanel,
    ImportPanel,
    PipelineHeaderWidget,
    _make_divider,
)
