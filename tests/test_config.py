from __future__ import annotations

from pathlib import Path

from github_backup_deck.config import AppConfig, ConfigStore


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    store = ConfigStore(path)
    expected = AppConfig(default_backup_directory=str(tmp_path / "backup"), fetch_lfs=False)
    store.save(expected)
    assert store.load() == expected
    assert path.stat().st_mode & 0o777 == 0o600


def test_default_config_when_file_missing(tmp_path: Path) -> None:
    assert ConfigStore(tmp_path / "missing.json").load() == AppConfig()
