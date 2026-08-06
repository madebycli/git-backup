from __future__ import annotations

import os
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from github_backup_deck.models import BackupFormat, Repository


class SnapshotWriter:
    def write(
        self,
        repository: Repository,
        mirror_path: Path,
        metadata_path: Path,
        snapshot_root: Path,
        backup_format: BackupFormat,
    ) -> Path:
        owner_parts = repository.full_name.split("/")[:-1]
        repository_root = snapshot_root / "repositories" / Path(*owner_parts)
        repository_root.mkdir(parents=True, exist_ok=True)
        if backup_format == "zip":
            return self._write_zip(repository, mirror_path, metadata_path, repository_root)
        return self._write_folder(repository, mirror_path, metadata_path, repository_root)

    @staticmethod
    def _write_zip(
        repository: Repository,
        mirror_path: Path,
        metadata_path: Path,
        repository_root: Path,
    ) -> Path:
        target = repository_root / f"{repository.name}.zip"
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{repository.name}.", suffix=".zip", dir=repository_root
        )
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with zipfile.ZipFile(
                temporary,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
                allowZip64=True,
            ) as archive:
                SnapshotWriter._add_tree(
                    archive, mirror_path, Path(f"{repository.name}.git")
                )
                SnapshotWriter._add_tree(archive, metadata_path, Path("metadata"))
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    @staticmethod
    def _write_folder(
        repository: Repository,
        mirror_path: Path,
        metadata_path: Path,
        repository_root: Path,
    ) -> Path:
        target = repository_root / repository.name
        temporary = repository_root / f".{repository.name}.{uuid.uuid4().hex}.tmp"
        try:
            temporary.mkdir(parents=True)
            shutil.copytree(mirror_path, temporary / "repository.git", symlinks=True)
            shutil.copytree(metadata_path, temporary / "metadata", symlinks=True)
            os.replace(temporary, target)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        return target

    @staticmethod
    def _add_tree(archive: zipfile.ZipFile, source: Path, prefix: Path) -> None:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            archive_name = (prefix / relative).as_posix()
            if path.is_dir():
                archive.writestr(f"{archive_name}/", b"")
            elif path.is_file():
                archive.write(path, archive_name)
