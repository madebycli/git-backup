import zipfile
from pathlib import Path

from github_backup_deck.backup.snapshot import SnapshotWriter
from github_backup_deck.models import Repository


def test_repository_zip_contains_mirror_and_metadata(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror.git"
    mirror.mkdir()
    (mirror / "HEAD").write_text("ref: refs/heads/main\n")
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    (metadata / "repository.json").write_text("{}\n")
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    repository = Repository("demo", "owner/demo", "https://example.invalid/demo.git")

    target = SnapshotWriter().write(repository, mirror, metadata, snapshot, "zip")

    with zipfile.ZipFile(target) as archive:
        assert "demo.git/HEAD" in archive.namelist()
        assert "metadata/repository.json" in archive.namelist()


def test_repository_folder_contains_mirror_and_metadata(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror.git"
    mirror.mkdir()
    (mirror / "HEAD").write_text("head\n")
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    (metadata / "repository.json").write_text("{}\n")
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    repository = Repository("demo", "owner/demo", "https://example.invalid/demo.git")

    target = SnapshotWriter().write(repository, mirror, metadata, snapshot, "folder")

    assert (target / "repository.git" / "HEAD").is_file()
    assert (target / "metadata" / "repository.json").is_file()
