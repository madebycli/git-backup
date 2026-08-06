import zipfile
from pathlib import Path

import pytest

from github_backup_deck.backup.snapshot import SnapshotWriter
from github_backup_deck.models import Repository


def _source(tmp_path: Path) -> tuple[Path, Path, Repository]:
    mirror = tmp_path / "mirror.git"
    mirror.mkdir()
    (mirror / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    (metadata / "repository.json").write_text(
        '{"full_name":"owner/demo"}\n',
        encoding="utf-8",
    )
    repository = Repository("demo", "owner/demo", "https://example.invalid/demo.git")
    return mirror, metadata, repository


def test_repository_zip_contains_only_verified_export(tmp_path: Path) -> None:
    mirror, metadata, repository = _source(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    target = SnapshotWriter().write(repository, mirror, metadata, snapshot, "zip")

    with zipfile.ZipFile(target) as archive:
        assert "repository.git/HEAD" in archive.namelist()
        assert "metadata/repository.json" in archive.namelist()
        assert "backup-manifest.json" in archive.namelist()


def test_repository_folder_contains_only_verified_export(tmp_path: Path) -> None:
    mirror, metadata, repository = _source(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    target = SnapshotWriter().write(repository, mirror, metadata, snapshot, "folder")

    assert (target / "repository.git" / "HEAD").is_file()
    assert (target / "metadata" / "repository.json").is_file()
    assert (target / "backup-manifest.json").is_file()


def test_repository_export_rejects_symlink_source(tmp_path: Path) -> None:
    mirror, metadata, repository = _source(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (mirror / "unsafe").symlink_to(outside)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()

    with pytest.raises(RuntimeError, match="unsafe symlink"):
        SnapshotWriter().write(repository, mirror, metadata, snapshot, "zip")
