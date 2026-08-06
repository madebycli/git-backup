from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path

from github_backup_deck.backup.verifier import verify_export
from github_backup_deck.models import BackupFormat, Repository
from github_backup_deck.process import CommandCancelled


class SnapshotWriter:
    def write(
        self,
        repository: Repository,
        mirror_path: Path,
        metadata_path: Path,
        export_root: Path,
        backup_format: BackupFormat,
        *,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        owner_parts = repository.full_name.split("/")[:-1]
        repository_root = export_root / "repositories" / Path(*owner_parts)
        repository_root.mkdir(parents=True, exist_ok=True)
        manifest = self._build_manifest(mirror_path, metadata_path, cancel_event)
        if backup_format == "zip":
            target = self._write_zip(
                repository,
                mirror_path,
                metadata_path,
                repository_root,
                manifest,
                cancel_event,
            )
        else:
            target = self._write_folder(
                repository,
                mirror_path,
                metadata_path,
                repository_root,
                manifest,
                cancel_event,
            )
        verify_export(target, backup_format, cancel_event=cancel_event)
        return target

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise CommandCancelled("Backup cancelled while creating repository export")

    @classmethod
    def _build_manifest(
        cls,
        mirror_path: Path,
        metadata_path: Path,
        cancel_event: threading.Event | None,
    ) -> dict[str, dict[str, int | str]]:
        manifest: dict[str, dict[str, int | str]] = {}
        for source, prefix in (
            (mirror_path, Path("repository.git")),
            (metadata_path, Path("metadata")),
        ):
            for path in sorted(source.rglob("*")):
                cls._check_cancel(cancel_event)
                if path.is_symlink():
                    raise RuntimeError(f"Refusing unsafe symlink in backup source: {path}")
                if not path.is_file():
                    continue
                relative = (prefix / path.relative_to(source)).as_posix()
                digest = hashlib.sha256()
                with path.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        cls._check_cancel(cancel_event)
                        digest.update(chunk)
                manifest[relative] = {
                    "size": path.stat().st_size,
                    "sha256": digest.hexdigest(),
                }
        return manifest

    @classmethod
    def _write_zip(
        cls,
        repository: Repository,
        mirror_path: Path,
        metadata_path: Path,
        repository_root: Path,
        manifest: dict[str, dict[str, int | str]],
        cancel_event: threading.Event | None,
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
                cls._add_tree(archive, mirror_path, Path("repository.git"), cancel_event)
                cls._add_tree(archive, metadata_path, Path("metadata"), cancel_event)
                archive.writestr(
                    "backup-manifest.json",
                    json.dumps({"files": manifest}, indent=2, sort_keys=True) + "\n",
                )
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    @classmethod
    def _write_folder(
        cls,
        repository: Repository,
        mirror_path: Path,
        metadata_path: Path,
        repository_root: Path,
        manifest: dict[str, dict[str, int | str]],
        cancel_event: threading.Event | None,
    ) -> Path:
        target = repository_root / repository.name
        temporary = repository_root / f".{repository.name}.{uuid.uuid4().hex}.tmp"
        try:
            temporary.mkdir(parents=True)
            cls._copy_tree(mirror_path, temporary / "repository.git", cancel_event)
            cls._copy_tree(metadata_path, temporary / "metadata", cancel_event)
            (temporary / "backup-manifest.json").write_text(
                json.dumps({"files": manifest}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, target)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)
        return target

    @classmethod
    def _copy_tree(
        cls,
        source: Path,
        destination: Path,
        cancel_event: threading.Event | None,
    ) -> None:
        destination.mkdir(parents=True)
        for path in sorted(source.rglob("*")):
            cls._check_cancel(cancel_event)
            if path.is_symlink():
                raise RuntimeError(f"Refusing unsafe symlink in backup source: {path}")
            target = destination / path.relative_to(source)
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                cls._copy_file(path, target, cancel_event)

    @classmethod
    def _copy_file(
        cls,
        source: Path,
        target: Path,
        cancel_event: threading.Event | None,
    ) -> None:
        with source.open("rb") as source_handle, target.open("wb") as target_handle:
            while chunk := source_handle.read(1024 * 1024):
                cls._check_cancel(cancel_event)
                target_handle.write(chunk)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        shutil.copystat(source, target, follow_symlinks=False)

    @classmethod
    def _add_tree(
        cls,
        archive: zipfile.ZipFile,
        source: Path,
        prefix: Path,
        cancel_event: threading.Event | None,
    ) -> None:
        for path in sorted(source.rglob("*")):
            cls._check_cancel(cancel_event)
            if path.is_symlink():
                raise RuntimeError(f"Refusing unsafe symlink in backup source: {path}")
            relative = path.relative_to(source)
            archive_name = (prefix / relative).as_posix()
            if path.is_dir():
                archive.writestr(f"{archive_name}/", b"")
            elif path.is_file():
                with (
                    path.open("rb") as source_handle,
                    archive.open(archive_name, "w", force_zip64=True) as target_handle,
                ):
                    while chunk := source_handle.read(1024 * 1024):
                        cls._check_cancel(cancel_event)
                        target_handle.write(chunk)
