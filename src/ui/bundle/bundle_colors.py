"""Bundle-specific color palette.

These keys are NOT identical to ThemeManager.get_colors() — do not merge.
"""


def get_bundle_colors(dark_mode: bool) -> dict[str, str]:
    """Return the full color palette for bundle UI components."""
    if dark_mode:
        return {
            # Backgrounds
            "bg_primary": "#1e293b",
            "bg_secondary": "#0f172a",
            "bg_tertiary": "#334155",
            "bg_input": "#1e293b",
            "bg_hover": "#334155",
            # Text
            "text_primary": "#f1f5f9",
            "text_secondary": "#cbd5e1",
            "text_tertiary": "#94a3b8",
            "text_disabled": "#64748b",
            # Borders
            "border": "#475569",
            "border_light": "#334155",
            "border_focus": "#3b82f6",
            # States
            "hover": "#334155",
            "selected": "#3b82f6",
            "active": "#2563eb",
            # Semantic
            "danger": "#ef4444",
            "danger_hover": "#dc2626",
            "success": "#10b981",
            "success_hover": "#059669",
            "warning": "#f59e0b",
            "warning_hover": "#d97706",
            "info": "#3b82f6",
            "info_hover": "#2563eb",
            # Component-specific
            "thumbnail_border": "#475569",
            "thumbnail_selected": "#3b82f6",
            "preview_bg": "#0f172a",
            "metadata_bg": "#1e293b",
            "button_bg": "#334155",
            "button_text": "#f1f5f9",
            "button_hover": "#475569",
        }
    return {
        # Backgrounds
        "bg_primary": "#ffffff",
        "bg_secondary": "#f9fafb",
        "bg_tertiary": "#f3f4f6",
        "bg_input": "#ffffff",
        "bg_hover": "#f3f4f6",
        # Text
        "text_primary": "#111827",
        "text_secondary": "#374151",
        "text_tertiary": "#6b7280",
        "text_disabled": "#9ca3af",
        # Borders
        "border": "#e5e7eb",
        "border_light": "#f3f4f6",
        "border_focus": "#3b82f6",
        # States
        "hover": "#f3f4f6",
        "selected": "#1e88e5",
        "active": "#1976d2",
        # Semantic
        "danger": "#ef4444",
        "danger_hover": "#dc2626",
        "success": "#10b981",
        "success_hover": "#059669",
        "warning": "#f59e0b",
        "warning_hover": "#d97706",
        "info": "#3b82f6",
        "info_hover": "#2563eb",
        # Component-specific
        "thumbnail_border": "#d1d5db",
        "thumbnail_selected": "#3b82f6",
        "preview_bg": "#ffffff",
        "metadata_bg": "#f9fafb",
        "button_bg": "#f3f4f6",
        "button_text": "#111827",
        "button_hover": "#e5e7eb",
    }


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a ``#rrggbb`` hex color string to an ``(r, g, b)`` tuple."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b)
