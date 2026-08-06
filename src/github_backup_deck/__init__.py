"""GitHub Backup Deck."""

from __future__ import annotations

from pathlib import Path

__all__ = ["__version__"]

_VERSION_FILE = Path(__file__).with_name("VERSION")
__version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
