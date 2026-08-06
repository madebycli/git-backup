from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path

from github_backup_deck.backup.git_mirror import GitMirror
from github_backup_deck.backup.metadata import MetadataWriter
from github_backup_deck.events import EventSink, ProgressEvent, null_sink
from github_backup_deck.models import (
    BackupPlan,
    BackupSummary,
    RepositoryResult,
    utc_now,
)
from github_backup_deck.state import StateStore


class BackupRunner:
    def __init__(
        self,
        *,
        mirror: GitMirror | None = None,
        metadata: MetadataWriter | None = None,
        state: StateStore | None = None,
    ) -> None:
        self.mirror = mirror or GitMirror()
        self.metadata = metadata or MetadataWriter()
        self.state = state or StateStore()

    def run(self, plan: BackupPlan, sink: EventSink = null_sink) -> BackupSummary:
        run_id = uuid.uuid4().hex
        started_at = utc_now()
        destination = plan.destination
        destination.mkdir(parents=True, exist_ok=True)
        results: list[RepositoryResult] = []
        total = len(plan.repositories)
        sink(ProgressEvent("info", f"Starting backup of {total} repositories", total=total))
        for index, repository in enumerate(plan.repositories, start=1):
            sink(
                ProgressEvent(
                    "progress",
                    f"Backing up {repository.full_name}",
                    repository=repository.full_name,
                    current=index,
                    total=total,
                )
            )
            mirror_path = destination / "repositories" / f"{repository.full_name}.git"
            metadata_path = destination / "metadata" / repository.full_name
            try:
                mirror_path = self.mirror.sync(
                    repository,
                    destination,
                    fetch_lfs=plan.options.fetch_lfs,
                )
                metadata_path = self.metadata.write(repository, destination, plan.options)
                results.append(
                    RepositoryResult(
                        repository.full_name,
                        "ok",
                        str(mirror_path),
                        str(metadata_path),
                    )
                )
                sink(
                    ProgressEvent(
                        "success",
                        f"Finished {repository.full_name}",
                        repository=repository.full_name,
                        current=index,
                        total=total,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - per-repository isolation is intentional
                results.append(
                    RepositoryResult(
                        repository.full_name,
                        "failed",
                        str(mirror_path),
                        str(metadata_path),
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
        finished_at = utc_now()
        summary = BackupSummary(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            destination=str(destination),
            repositories_total=total,
            repositories_ok=sum(item.status == "ok" for item in results),
            repositories_failed=sum(item.status == "failed" for item in results),
            results=tuple(results),
        )
        self._write_manifest(destination, summary)
        self.state.record_summary(summary)
        sink(
            ProgressEvent(
                "success" if summary.repositories_failed == 0 else "warning",
                (
                    f"Backup finished: {summary.repositories_ok} succeeded, "
                    f"{summary.repositories_failed} failed"
                ),
                current=total,
                total=total,
            )
        )
        return summary

    @staticmethod
    def _write_manifest(destination: Path, summary: BackupSummary) -> None:
        manifests = destination / "manifests"
        manifests.mkdir(parents=True, exist_ok=True)
        path = manifests / f"{summary.run_id}.json"
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=manifests)
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
