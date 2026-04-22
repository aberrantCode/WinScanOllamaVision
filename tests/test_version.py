"""Sanity tests for the app version module."""

from __future__ import annotations

import re

from packaging.version import InvalidVersion, Version


def test_version_is_pep440_compatible():
    import __version__ as version_module

    try:
        Version(version_module.__version__)
    except InvalidVersion as exc:
        raise AssertionError(
            f"Version {version_module.__version__!r} is not PEP 440 compatible"
        ) from exc


def test_version_matches_expected_shape():
    import __version__ as version_module

    assert re.match(
        r"^\d+\.\d+\.\d+([-.]?(?:alpha|beta|rc|dev|post)\d*)?$",
        version_module.__version__,
    ), version_module.__version__
