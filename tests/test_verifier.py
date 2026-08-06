from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from github_backup_deck.backup.snapshot import SnapshotWriter
from github_backup_deck.backup.verifier import verify_destination, verify_export
from github_backup_deck.models import Repository


def _export(tmp_path: Path, backup_format: str) -> Path:
    mirror = tmp_path / "mirror.git"
    mirror.mkdir()
    (mirror / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    (metadata / "repository.json").write_text(
        '{"full_name":"owner/demo"}\n',
        encoding="utf-8",
    )
    root = tmp_path / "export"
    root.mkdir()
    repository = Repository("demo", "owner/demo", "https://example.invalid/demo.git")
    return SnapshotWriter().write(  # type: ignore[arg-type]
        repository,
        mirror,
        metadata,
        root,
        backup_format,
    )


def test_empty_destination_is_valid(tmp_path: Path) -> None:
    result = verify_destination(tmp_path)
    assert result.ok
    assert result.mirrors_checked == 0


def test_folder_verification_rejects_unexpected_file(tmp_path: Path) -> None:
    target = _export(tmp_path, "folder")
    (target / "unexpected.txt").write_text("not in manifest", encoding="utf-8")

    with pytest.raises(RuntimeError, match="does not exactly match"):
        verify_export(target, "folder")


def test_zip_verification_rejects_unexpected_member(tmp_path: Path) -> None:
    target = _export(tmp_path, "zip")
    with zipfile.ZipFile(target, "a") as archive:
        archive.writestr("unexpected.txt", "not in manifest")

    with pytest.raises(RuntimeError, match="does not exactly match"):
        verify_export(target, "zip")
