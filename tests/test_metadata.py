from __future__ import annotations

import json
from pathlib import Path

from github_backup_deck.backup import metadata


def test_atomic_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "items.jsonl"
    metadata._atomic_jsonl(path, [{"id": 1}, {"id": 2}])
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows == [{"id": 1}, {"id": 2}]
