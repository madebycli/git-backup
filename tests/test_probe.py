from __future__ import annotations

from pathlib import Path

from github_backup_deck.storage.probe import probe_path


def test_probe_creates_and_writes_directory(tmp_path: Path) -> None:
    destination = tmp_path / "backup"
    result = probe_path(destination)
    assert result.ok
    assert destination.is_dir()
    assert result.free_bytes > 0
