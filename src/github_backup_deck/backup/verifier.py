from __future__ import annotations

import json
import threading
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, BinaryIO

from github_backup_deck.models import BackupFormat, Repository
from github_backup_deck.process import CommandCancelled, run_command


@dataclass(frozen=True, slots=True)
class VerificationResult:
    destination: str
    mirrors_checked: int
    mirrors_failed: int
    missing_metadata: int
    exports_checked: int
    exports_failed: int
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return (
            self.mirrors_failed == 0
            and self.missing_metadata == 0
            and self.exports_failed == 0
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = self.ok
        return payload


def _parse_refs(text: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    for raw in text.splitlines():
        parts = raw.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        sha, ref = parts
        if ref == "HEAD" or not ref.startswith("refs/"):
            continue
        refs[ref] = sha
    return refs


def _missing_remote_refs(
    repository: Repository,
    mirror: Path,
    *,
    cancel_event: threading.Event | None,
) -> list[str]:
    remote = run_command(
        ["git", "ls-remote", repository.clone_url],
        timeout=600,
        cancel_event=cancel_event,
    )
    local = run_command(
        ["git", "-C", str(mirror), "show-ref", "--dereference"],
        timeout=120,
        cancel_event=cancel_event,
        check=False,
    )
    remote_refs = _parse_refs(remote.stdout)
    local_refs = _parse_refs(local.stdout)
    return sorted(ref for ref, sha in remote_refs.items() if local_refs.get(ref) != sha)


def verify_mirror(
    repository: Repository,
    mirror: Path,
    metadata: Path,
    *,
    fetch_lfs: bool,
    cancel_event: threading.Event | None = None,
) -> None:
    run_command(
        ["git", "-C", str(mirror), "fsck", "--full"],
        timeout=1800,
        cancel_event=cancel_event,
    )
    missing = _missing_remote_refs(repository, mirror, cancel_event=cancel_event)
    if missing:
        run_command(
            ["git", "-C", str(mirror), "remote", "update", "--prune"],
            timeout=3600,
            cancel_event=cancel_event,
        )
        if fetch_lfs:
            run_command(
                ["git", "-C", str(mirror), "lfs", "fetch", "--all"],
                timeout=7200,
                cancel_event=cancel_event,
            )
        missing = _missing_remote_refs(repository, mirror, cancel_event=cancel_event)
    if missing:
        preview = ", ".join(missing[:8])
        suffix = " …" if len(missing) > 8 else ""
        raise RuntimeError(
            f"Mirror verification failed for {repository.full_name}; "
            f"{len(missing)} refs missing or stale: {preview}{suffix}"
        )
    if fetch_lfs:
        run_command(
            ["git", "-C", str(mirror), "lfs", "fsck", "--objects"],
            timeout=1800,
            cancel_event=cancel_event,
        )
    verify_metadata(metadata)


def verify_metadata(metadata: Path) -> None:
    repository_file = metadata / "repository.json"
    if not repository_file.is_file():
        raise RuntimeError(f"Missing repository metadata: {repository_file}")
    try:
        payload = json.loads(repository_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid repository metadata: {repository_file}: {exc}") from exc
    if not isinstance(payload, dict) or not payload.get("full_name"):
        raise RuntimeError(f"Repository metadata has no full_name: {repository_file}")
    for path in metadata.glob("*.jsonl"):
        number = 0
        try:
            with path.open(encoding="utf-8") as handle:
                for number, line in enumerate(handle, start=1):
                    if line.strip():
                        value = json.loads(line)
                        if not isinstance(value, dict):
                            raise ValueError("line is not an object")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"Invalid JSONL metadata {path}:{number}: {exc}") from exc


def _verify_hash(
    expected: str,
    chunks: BinaryIO,
    cancel_event: threading.Event | None,
) -> None:
    import hashlib

    digest = hashlib.sha256()
    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise CommandCancelled("Backup cancelled during final verification")
        chunk = chunks.read(1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    if digest.hexdigest() != expected:
        raise RuntimeError("Export checksum mismatch")


def _manifest_files(payload: object, description: str) -> dict[str, dict[str, Any]]:
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, dict):
        raise RuntimeError(f"{description} has no valid checksum manifest")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_name, raw_details in files.items():
        name = str(raw_name)
        if not name or name.startswith("/") or ".." in Path(name).parts:
            raise RuntimeError(f"{description} contains an unsafe manifest path: {name}")
        if not isinstance(raw_details, dict):
            raise RuntimeError(f"{description} has invalid manifest details: {name}")
        expected_hash = raw_details.get("sha256")
        expected_size = raw_details.get("size")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise RuntimeError(f"{description} has an invalid checksum: {name}")
        if not isinstance(expected_size, int) or expected_size < 0:
            raise RuntimeError(f"{description} has an invalid size: {name}")
        normalized[name] = raw_details
    return normalized


def verify_export(
    path: Path,
    backup_format: BackupFormat,
    *,
    cancel_event: threading.Event | None = None,
) -> None:
    if backup_format == "zip":
        if not path.is_file():
            raise RuntimeError(f"Missing ZIP snapshot: {path}")
        try:
            with zipfile.ZipFile(path) as archive:
                manifest_payload = json.loads(archive.read("backup-manifest.json"))
                files = _manifest_files(manifest_payload, "ZIP snapshot")
                file_infos = {
                    info.filename: info
                    for info in archive.infolist()
                    if not info.is_dir() and info.filename != "backup-manifest.json"
                }
                expected_names = set(files)
                actual_names = set(file_infos)
                if actual_names != expected_names:
                    missing = sorted(expected_names - actual_names)
                    extra = sorted(actual_names - expected_names)
                    raise RuntimeError(
                        "ZIP content does not exactly match its manifest; "
                        f"missing={missing[:5]}, extra={extra[:5]}"
                    )
                for name, details in files.items():
                    info = file_infos[name]
                    if info.file_size != details["size"]:
                        raise RuntimeError(f"ZIP size mismatch: {name}")
                    with archive.open(info) as handle:
                        _verify_hash(str(details["sha256"]), handle, cancel_event)
        except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            raise RuntimeError(f"Invalid ZIP snapshot {path}: {exc}") from exc
        return

    if not path.is_dir():
        raise RuntimeError(f"Missing folder snapshot: {path}")
    manifest_path = path / "backup-manifest.json"
    try:
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid folder checksum manifest: {exc}") from exc
    files = _manifest_files(manifest_payload, "Folder snapshot")
    actual_files = {
        item.relative_to(path).as_posix()
        for item in path.rglob("*")
        if item.is_file() and not item.is_symlink() and item != manifest_path
    }
    expected_files = set(files)
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        raise RuntimeError(
            "Folder content does not exactly match its manifest; "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )
    root = path.resolve()
    for name, details in files.items():
        target = (path / name).resolve()
        if not target.is_relative_to(root) or target.is_symlink() or not target.is_file():
            raise RuntimeError(f"Folder snapshot has an unsafe or missing entry: {name}")
        if target.stat().st_size != details["size"]:
            raise RuntimeError(f"Folder size mismatch: {name}")
        with target.open("rb") as handle:
            _verify_hash(str(details["sha256"]), handle, cancel_event)


def verify_destination(destination: Path) -> VerificationResult:
    destination = destination.expanduser().resolve()
    errors: list[str] = []
    export_count = 0
    export_failed = 0
    roots: list[Path] = []
    current = destination / "current"
    if (current / "manifest.json").is_file():
        roots.append(current)
    runs = destination / "runs"
    if runs.is_dir():
        roots.extend(
            path
            for path in sorted(runs.iterdir())
            if path.is_dir() and (path / "manifest.json").is_file()
        )
    for root in roots:
        repository_root = root / "repositories"
        zip_exports = sorted(repository_root.glob("*/*.zip"))
        folder_exports = sorted(
            path
            for path in repository_root.glob("*/*")
            if path.is_dir() and (path / "backup-manifest.json").is_file()
        )
        if zip_exports and folder_exports:
            export_failed += 1
            errors.append(f"Mixed ZIP and folder outputs in one run: {root}")
        for export in zip_exports:
            export_count += 1
            try:
                verify_export(export, "zip")
            except RuntimeError as exc:
                export_failed += 1
                errors.append(f"{export}: {exc}")
        for export in folder_exports:
            export_count += 1
            try:
                verify_export(export, "folder")
            except RuntimeError as exc:
                export_failed += 1
                errors.append(f"{export}: {exc}")

    repositories_root = destination / "repositories"
    mirrors = sorted(repositories_root.glob("*/*.git")) if repositories_root.exists() else []
    failed = 0
    missing_metadata = 0
    for mirror in mirrors:
        result = run_command(
            ["git", "-C", str(mirror), "fsck", "--full"],
            timeout=1800,
            check=False,
        )
        if result.returncode != 0:
            failed += 1
            errors.append(f"{mirror}: {result.stderr.strip() or 'git fsck failed'}")
        relative = mirror.relative_to(repositories_root)
        full_name = str(relative)[:-4]
        metadata = destination / "metadata" / full_name / "repository.json"
        if not metadata.is_file():
            missing_metadata += 1
            errors.append(f"Missing metadata: {metadata}")
    return VerificationResult(
        str(destination),
        len(mirrors),
        failed,
        missing_metadata,
        export_count,
        export_failed,
        tuple(errors),
    )
