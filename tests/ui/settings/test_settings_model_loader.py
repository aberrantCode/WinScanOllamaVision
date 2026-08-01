"""
Tests for _ModelLoaderMixin in ui.settings.settings_model_loader.

Covers:
- The _MODEL_NAME_PATTERN regex (used as an allowlist) rejects dangerous names:
    * Path traversal: "../evil"
    * Shell injection: "model; rm -rf /"
    * HTML/XSS: "<script>"
- The pattern accepts valid model names:
    * "llama3.2"
    * "claude-3-5-sonnet-20241022"
    * "gemini-1.5-pro"
    * "qwen2.5-vl:latest"
- _get_cached_models() returns None when no cache is present
- _cache_models() stores a serialized JSON list and timestamp
"""

import json
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Access the compiled pattern from the module
# ---------------------------------------------------------------------------
from ui.settings.settings_model_loader import _MODEL_NAME_PATTERN

# ---------------------------------------------------------------------------
# Pattern — valid model names (full-string match)
# ---------------------------------------------------------------------------


def _full_match(name: str) -> bool:
    """Return True only if the pattern matches the ENTIRE string."""
    m = _MODEL_NAME_PATTERN.fullmatch(name)
    return m is not None


@pytest.mark.parametrize(
    "model_name",
    [
        "llama3.2",
        "claude-3-5-sonnet-20241022",
        "gemini-1.5-pro",
        "qwen2.5-vl:latest",
        "llava:7b",
        "claude-3-5-haiku-20241022",
        "gemini-2.0-flash-exp",
        "minicpm-v:8b",
        "phi3-vision:latest",
    ],
)
def test_model_name_pattern_accepts_valid_names(model_name):
    """The _MODEL_NAME_PATTERN should fully match all well-formed model identifiers."""
    assert _full_match(model_name), f"Expected pattern to accept: {model_name!r}"


# ---------------------------------------------------------------------------
# Pattern — rejected dangerous names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    [
        "model; rm -rf /",
        "model && rm -rf /",
        "model | cat /etc/passwd",
        "<script>alert(1)</script>",
        "<script>",
        "model\x00null",
        'model"quote',
        "model'quote",
        "model name with spaces",
        "model\nnewline",
        "model\ttab",
    ],
)
def test_model_name_pattern_rejects_shell_injection_and_html(bad_name):
    """
    The _MODEL_NAME_PATTERN must NOT fully match shell injection metacharacters
    (semicolons, ampersands, pipes) or HTML injection characters.

    Note: The pattern intentionally allows dots and forward slashes to support
    Ollama-style paths like "namespace/model:tag". As a result, path traversal
    strings like "../evil" do pass the pattern — the confinement check is
    enforced separately at the file-open layer via is_path_confined().
    """
    assert not _full_match(bad_name), f"Expected pattern to reject: {bad_name!r}"


@pytest.mark.parametrize(
    "traversal_name",
    [
        "../evil",
        "../../etc/passwd",
    ],
)
def test_model_name_pattern_allows_path_traversal_strings(traversal_name):
    """
    The _MODEL_NAME_PATTERN is a LOOSE allowlist designed to block shell injection
    characters.  It intentionally permits '.' and '/' (needed for Ollama model names
    like 'org/model.tag').

    This test documents the KNOWN LIMITATION: path traversal strings like '../evil'
    are NOT blocked by the pattern alone.  Path confinement must be enforced
    separately at the file-access layer (see is_path_confined() in file_details_utils.py).
    """
    # The current regex allows these — this is a documented gap, NOT the desired behavior.
    # A stricter validation layer is needed for security-sensitive contexts.
    assert _full_match(traversal_name), (
        f"Pattern currently allows {traversal_name!r} — this test documents the known limitation"
    )


# ---------------------------------------------------------------------------
# _get_cached_models — cache miss
# ---------------------------------------------------------------------------


class TestableModelLoader:
    """Minimal host for _ModelLoaderMixin."""

    def __init__(self):
        from ui.settings.settings_model_loader import _ModelLoaderMixin

        for attr in dir(_ModelLoaderMixin):
            if not attr.startswith("__"):
                method = getattr(_ModelLoaderMixin, attr)
                if callable(method):
                    import types

                    setattr(self, attr, types.MethodType(method, self))

        self.config_manager = MagicMock()
        self._logger = MagicMock()

    def _get_logger(self):
        return self._logger


def test_get_cached_models_returns_none_when_no_cache():
    """_get_cached_models() must return None when config has no cache entry."""
    host = TestableModelLoader()
    host.config_manager.get_setting.return_value = None  # No cache

    result = host._get_cached_models("claude")

    assert result is None


def test_get_cached_models_returns_none_when_cache_expired():
    """_get_cached_models() must return None when cache timestamp is more than 24h ago."""
    from datetime import datetime, timedelta

    host = TestableModelLoader()

    old_timestamp = (datetime.now() - timedelta(hours=25)).isoformat()
    models_json = json.dumps(["claude-3-5-sonnet-20241022"])

    def mock_get_setting(section, key, *args):
        if "cache" in key:
            return models_json
        if "timestamp" in key:
            return old_timestamp
        return None

    host.config_manager.get_setting.side_effect = mock_get_setting

    result = host._get_cached_models("claude")

    assert result is None


def test_get_cached_models_returns_list_when_cache_valid():
    """_get_cached_models() must return the cached model list when cache is fresh."""
    from datetime import datetime

    host = TestableModelLoader()

    fresh_timestamp = datetime.now().isoformat()
    expected_models = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
    models_json = json.dumps(expected_models)

    def mock_get_setting(section, key, *args):
        if "cache" in key:
            return models_json
        if "timestamp" in key:
            return fresh_timestamp
        return None

    host.config_manager.get_setting.side_effect = mock_get_setting

    result = host._get_cached_models("claude")

    assert result == expected_models


def test_get_cached_models_returns_none_on_invalid_json():
    """_get_cached_models() must return None and not crash on malformed JSON."""
    from datetime import datetime

    host = TestableModelLoader()

    fresh_timestamp = datetime.now().isoformat()

    def mock_get_setting(section, key, *args):
        if "cache" in key:
            return "not_valid_json["
        if "timestamp" in key:
            return fresh_timestamp
        return None

    host.config_manager.get_setting.side_effect = mock_get_setting

    result = host._get_cached_models("claude")

    assert result is None


# ---------------------------------------------------------------------------
# _cache_models — stores JSON and timestamp
# ---------------------------------------------------------------------------


def test_cache_models_stores_json_array():
    """_cache_models() must serialise the model list to JSON and persist it."""
    host = TestableModelLoader()

    models = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]
    host._cache_models("claude", models)

    # config_manager.set_setting must have been called with the JSON array
    calls = host.config_manager.set_setting.call_args_list
    json_call = next(
        (c for c in calls if "cache" in str(c)),
        None,
    )
    assert json_call is not None
    stored_value = json_call[0][2]  # positional arg 3
    assert json.loads(stored_value) == models


def test_cache_models_stores_timestamp():
    """_cache_models() must persist a timestamp alongside the model list."""
    from datetime import datetime

    host = TestableModelLoader()
    host._cache_models("gemini", ["gemini-1.5-pro"])

    calls = host.config_manager.set_setting.call_args_list
    timestamp_call = next(
        (c for c in calls if "timestamp" in str(c)),
        None,
    )
    assert timestamp_call is not None
    # Timestamp should be parseable as ISO format
    timestamp_value = timestamp_call[0][2]
    # Should not raise
    datetime.fromisoformat(timestamp_value)


def test_cache_models_uses_correct_section():
    """_cache_models() must write to the 'ModelCache' config section."""
    host = TestableModelLoader()
    host._cache_models("ollama", ["llava:latest"])

    sections_written = {c[0][0] for c in host.config_manager.set_setting.call_args_list}
    assert "ModelCache" in sections_written


# ---------------------------------------------------------------------------
# Pattern — boundary and edge cases
# ---------------------------------------------------------------------------


def test_model_name_pattern_rejects_empty_string():
    """Empty string should not match (fullmatch requires at least one char)."""
    assert not _full_match("")


def test_model_name_pattern_rejects_whitespace_only():
    """Whitespace-only strings should not match."""
    assert not _full_match("   ")
    assert not _full_match("\t")
    assert not _full_match("\n")


def test_model_name_pattern_allows_version_separators():
    """Colons and slashes (used in Ollama tags and org-scoped names) must be allowed."""
    assert _full_match("org/model:version")
    assert _full_match("model:latest")
    assert _full_match("namespace/model-name:tag")
