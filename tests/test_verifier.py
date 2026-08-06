from __future__ import annotations

from pathlib import Path

from github_backup_deck.backup.verifier import verify_destination


def test_empty_destination_is_valid(tmp_path: Path) -> None:
    result = verify_destination(tmp_path)
    assert result.ok
    assert result.mirrors_checked == 0
