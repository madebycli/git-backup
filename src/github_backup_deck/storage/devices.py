from __future__ import annotations

import os
from pathlib import Path

from github_backup_deck.storage.location import StorageLocation


def discover_locations() -> list[StorageLocation]:
    home = Path.home()
    candidates = [StorageLocation(home / "GitHub Backup", "GitHub Backup", "home")]
    username = home.name
    for base in (Path("/run/media") / username, Path("/media") / username, Path("/mnt")):
        if not base.is_dir():
            continue
        try:
            entries = sorted(base.iterdir(), key=lambda path: path.name.casefold())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir() and os.access(entry, os.W_OK):
                candidates.append(StorageLocation(entry / "GitHub Backup", entry.name, "external"))
    unique: dict[Path, StorageLocation] = {}
    for candidate in candidates:
        unique[candidate.path] = candidate
    return list(unique.values())
