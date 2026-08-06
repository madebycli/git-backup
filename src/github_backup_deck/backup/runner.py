from __future__ import annotations

import fcntl
import json
import os
import shutil
import tempfile
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from github_backup_deck.backup.git_mirror import GitMirror
from github_backup_deck.backup.metadata import MetadataWriter
from github_backup_deck.backup.snapshot import SnapshotWriter
from github_backup_deck.backup.verifier import verify_export, verify_mirror
from github_backup_deck.events import EventSink, ProgressEvent, null_sink
from github_backup_deck.models import BackupPlan, BackupSummary, RepositoryResult, utc_now
from github_backup_deck.process import CommandCancelled
from github_backup_deck.state import StateStore


class BackupRunner:
    def __init__(
        self,
        *,
        mirror: GitMirror | None = None,
        metadata: MetadataWriter | None = None,
        snapshot: SnapshotWriter | None = None,
        state: StateStore | None = None,
    ) -> None:
        self.mirror = mirror or GitMirror()
        self.metadata = metadata or MetadataWriter()
        self.snapshot = snapshot or SnapshotWriter()
        self.state = state or StateStore()

    def run(
        self,
        plan: BackupPlan,
        sink: EventSink = null_sink,
        *,
        cancel_event: threading.Event | None = None,
    ) -> BackupSummary:
        run_id = uuid.uuid4().hex
        started_at = utc_now()
        destination = plan.destination.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging_root = destination.parent / f".{destination.name}.github-backup-deck-staging"
        final_root = self._final_root(
            destination,
            started_at,
            run_id,
            plan.options.versioned_snapshots,
        )

        with self._destination_lock(destination):
            self._reset_staging(staging_root)
            workspace = staging_root / "work"
            publish_root = staging_root / "publish"
            workspace.mkdir(parents=True)
            publish_root.mkdir(parents=True)
            completed: list[tuple[str, Path]] = []
            failed: list[RepositoryResult] = []
            total = len(plan.repositories)
            try:
                sink(
                    ProgressEvent(
                        "info",
                        f"Preparing isolated backup of {total} repositories",
                        total=total,
                    )
                )
                for index, repository in enumerate(plan.repositories, start=1):
                    self._check_cancel(cancel_event)
                    sink(
                        ProgressEvent(
                            "progress",
                            "Downloading every Git ref into temporary staging",
                            repository=repository.full_name,
                            current=index,
                            total=total,
                        )
                    )
                    try:
                        mirror_path = self.mirror.sync(
                            repository,
                            workspace,
                            fetch_lfs=plan.options.fetch_lfs,
                            cancel_event=cancel_event,
                        )
                        self._check_cancel(cancel_event)
                        metadata_path = self.metadata.write(
                            repository,
                            workspace,
                            plan.options,
                            cancel_event=cancel_event,
                        )
                        sink(
                            ProgressEvent(
                                "info",
                                "Verifying refs, Git objects, LFS and metadata",
                                repository=repository.full_name,
                                current=index,
                                total=total,
                            )
                        )
                        verify_mirror(
                            repository,
                            mirror_path,
                            metadata_path,
                            fetch_lfs=plan.options.fetch_lfs,
                            cancel_event=cancel_event,
                        )
                        self._check_cancel(cancel_event)
                        export_path = self.snapshot.write(
                            repository,
                            mirror_path,
                            metadata_path,
                            publish_root,
                            plan.options.backup_format,
                            cancel_event=cancel_event,
                        )
                        completed.append(
                            (repository.full_name, export_path.relative_to(publish_root))
                        )
                        sink(
                            ProgressEvent(
                                "success",
                                f"Verified {plan.options.backup_format} export is ready",
                                repository=repository.full_name,
                                current=index,
                                total=total,
                            )
                        )
                    except CommandCancelled:
                        raise
                    except Exception as exc:  # noqa: BLE001 - per-repository isolation
                        failed.append(
                            RepositoryResult(
                                repository.full_name,
                                "failed",
                                "",
                                "",
                                None,
                                str(exc),
                            )
                        )
                        sink(
                            ProgressEvent(
                                "error",
                                str(exc),
                                repository=repository.full_name,
                                current=index,
                                total=total,
                            )
                        )

                self._check_cancel(cancel_event)
                if failed:
                    failed_by_name = {item.full_name: item for item in failed}
                    results = tuple(
                        failed_by_name.get(
                            repository.full_name,
                            RepositoryResult(
                                repository.full_name,
                                "skipped",
                                "",
                                "",
                                None,
                                "Verified in staging but not published because "
                                "another repository failed",
                            ),
                        )
                        for repository in plan.repositories
                    )
                    summary = self._summary(
                        run_id,
                        started_at,
                        destination,
                        results,
                        snapshot_path=None,
                    )
                    self._record_state(summary, sink)
                    sink(
                        ProgressEvent(
                            "error",
                            "Backup was not published because "
                            "verification was incomplete",
                            current=total,
                            total=total,
                        )
                    )
                    return summary

                result_items = tuple(
                    RepositoryResult(
                        full_name,
                        "ok",
                        "",
                        "",
                        str(final_root / relative),
                    )
                    for full_name, relative in completed
                )
                summary = self._summary(
                    run_id,
                    started_at,
                    destination,
                    result_items,
                    snapshot_path=str(final_root),
                )
                self._write_manifest(publish_root / "manifest.json", summary)
                for _full_name, relative in completed:
                    verify_export(
                        publish_root / relative,
                        plan.options.backup_format,
                        cancel_event=cancel_event,
                    )
                sink(
                    ProgressEvent(
                        "info",
                        "Publishing verified backup atomically",
                        current=total,
                        total=total,
                    )
                )
                previous = self._publish(
                    publish_root, final_root, plan.options.versioned_snapshots
                )
                try:
                    for _full_name, relative in completed:
                        verify_export(
                            final_root / relative,
                            plan.options.backup_format,
                            cancel_event=cancel_event,
                        )
                    self._verify_manifest(final_root / "manifest.json", run_id)
                except Exception:
                    self._rollback_publication(final_root, previous)
                    raise
                if previous is not None:
                    shutil.rmtree(previous, ignore_errors=True)
                self._record_state(summary, sink)
                sink(
                    ProgressEvent(
                        "success",
                        f"Backup published and re-verified at {final_root}",
                        current=total,
                        total=total,
                    )
                )
                return summary
            finally:
                self._reset_staging(staging_root)

    @staticmethod
    def _check_cancel(cancel_event: threading.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise CommandCancelled("Backup cancelled")

    @staticmethod
    @contextmanager
    def _destination_lock(destination: Path) -> Iterator[None]:
        lock_path = destination.parent / f".{destination.name}.github-backup-deck.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError(f"Another backup is already using {destination}") from exc
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def _reset_staging(path: Path) -> None:
        if path.exists():
            shutil.rmtree(path, ignore_errors=False)
        if path.exists():
            raise RuntimeError(f"Could not clear temporary staging directory: {path}")

    @staticmethod
    def _final_root(
        destination: Path,
        started_at: str,
        run_id: str,
        versioned: bool,
    ) -> Path:
        if not versioned:
            return destination / "current"
        timestamp = datetime.fromisoformat(started_at).strftime("%Y%m%d-%H%M%S")
        return destination / "runs" / f"{timestamp}-{run_id[:8]}"

    @staticmethod
    def _publish(source: Path, target: Path, versioned: bool) -> Path | None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if versioned:
            if target.exists():
                raise RuntimeError(f"Backup target already exists: {target}")
            os.replace(source, target)
            return None
        previous = target.with_name(f".{target.name}.previous-{uuid.uuid4().hex}")
        if target.exists():
            os.replace(target, previous)
        try:
            os.replace(source, target)
        except Exception:
            if previous.exists() and not target.exists():
                os.replace(previous, target)
            raise
        return previous if previous.exists() else None

    @staticmethod
    def _rollback_publication(target: Path, previous: Path | None) -> None:
        shutil.rmtree(target, ignore_errors=True)
        if previous is not None and previous.exists():
            os.replace(previous, target)

    @staticmethod
    def _summary(
        run_id: str,
        started_at: str,
        destination: Path,
        results: tuple[RepositoryResult, ...],
        snapshot_path: str | None,
    ) -> BackupSummary:
        return BackupSummary(
            run_id=run_id,
            started_at=started_at,
            finished_at=utc_now(),
            destination=str(destination),
            repositories_total=len(results),
            repositories_ok=sum(item.status == "ok" for item in results),
            repositories_failed=sum(item.status == "failed" for item in results),
            results=results,
            snapshot_path=snapshot_path,
        )

    def _record_state(self, summary: BackupSummary, sink: EventSink) -> None:
        try:
            self.state.record_summary(summary)
        except Exception as exc:  # noqa: BLE001 - backup data is already authoritative
            sink(
                ProgressEvent(
                    "warning",
                    f"Backup is valid, but local history could not be updated: {exc}",
                )
            )

    @staticmethod
    def _write_manifest(path: Path, summary: BackupSummary) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(summary.to_dict(), handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _verify_manifest(path: Path, run_id: str) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Published manifest is invalid: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("run_id") != run_id:
            raise RuntimeError("Published manifest does not match the completed backup")
