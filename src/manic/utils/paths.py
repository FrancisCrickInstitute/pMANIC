"""
Portable helpers to load bundled resources both in development and when the
application is "frozen" (packaged into an executable with PyInstaller or
similar tools).

Usage examples:

    from manic.utils.paths import resource_path, docs_path

    # Load QSS from package resources (src/manic/resources/style.qss)
    qss_file = resource_path('resources', 'style.qss')

    # Load a documentation markdown file from the top-level docs/ folder
    getting_started = docs_path('getting_started.md')

These helpers resolve paths correctly when running from source and when
running from a frozen executable (MEIPASS staging directory).
"""

from __future__ import annotations

import sys
from pathlib import Path


def _is_frozen() -> bool:
    """Return True when running from a frozen bundle (e.g., PyInstaller)."""
    return hasattr(sys, "_MEIPASS")


def _frozen_base() -> Path:
    """Base directory where bundled resources are unpacked when frozen."""
    # PyInstaller extracts bundled files into a temporary folder exposed as
    # sys._MEIPASS. Treat it as the base for all data lookups when frozen.
    return Path(getattr(sys, "_MEIPASS", ""))


def _package_base() -> Path:
    """Return the manic package root: .../src/manic."""
    # This file lives at .../src/manic/utils/paths.py
    # parents[0] = utils, [1] = manic, [2] = src, [3] = project root
    return Path(__file__).resolve().parents[1]


def _project_base() -> Path:
    """Return the project root directory (the folder that contains docs/)."""
    return Path(__file__).resolve().parents[3]


def resource_path(*parts: str) -> str:
    """
    Resolve a path inside the manic package resources (src/manic/resources).

    Example: resource_path('resources', 'style.qss')
    """
    if _is_frozen():
        base = _frozen_base()
        # In the frozen build we add package files preserving their relative
        # layout under the bundle; resources are typically under manic/resources
        return str(base.joinpath('src', 'manic', *parts)) if base.joinpath('src').exists() else str(base.joinpath('manic', *parts))
    # Dev: resolve from package root
    return str(_package_base().joinpath(*parts))


def docs_path(*parts: str) -> str:
    """
    Resolve a path inside the top-level docs/ directory.

    Example: docs_path('update_old_data.md')
    """
    if _is_frozen():
        base = _frozen_base()
        return str(base.joinpath('docs', *parts))
    return str(_project_base().joinpath('docs', *parts))


def project_path(*parts: str) -> str:
    """Resolve an absolute path relative to the project root directory."""
    if _is_frozen():
        # When frozen we typically do not expose project structure; fall back to base
        return str(_frozen_base().joinpath(*parts))
    return str(_project_base().joinpath(*parts))

