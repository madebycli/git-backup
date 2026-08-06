from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

BackupFormat = Literal["zip", "folder"]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class Repository:
    name: str
    full_name: str
    clone_url: str
    ssh_url: str | None = None
    default_branch: str | None = None
    private: bool = False
    archived: bool = False
    fork: bool = False
    updated_at: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Repository":
        return cls(
            name=str(payload["name"]),
            full_name=str(payload["full_name"]),
            clone_url=str(payload["clone_url"]),
            ssh_url=_optional_str(payload.get("ssh_url")),
            default_branch=_optional_str(payload.get("default_branch")),
            private=bool(payload.get("private", False)),
            archived=bool(payload.get("archived", False)),
            fork=bool(payload.get("fork", False)),
            updated_at=_optional_str(payload.get("updated_at")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BackupOptions:
    include_issues: bool = True
    include_pull_requests: bool = True
    include_releases: bool = True
    include_action_artifacts: bool = False
    include_archived: bool = True
    fetch_lfs: bool = True
    backup_format: BackupFormat = "zip"
    versioned_snapshots: bool = True


@dataclass(frozen=True, slots=True)
class BackupPlan:
    destination: Path
    repositories: tuple[Repository, ...]
    options: BackupOptions = field(default_factory=BackupOptions)


@dataclass(frozen=True, slots=True)
class RepositoryResult:
    full_name: str
    status: Literal["ok", "failed", "skipped"]
    mirror_path: str
    metadata_path: str
    snapshot_path: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class BackupSummary:
    run_id: str
    started_at: str
    finished_at: str
    destination: str
    repositories_total: int
    repositories_ok: int
    repositories_failed: int
    results: tuple[RepositoryResult, ...]
    snapshot_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["results"] = [asdict(item) for item in self.results]
        return data


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)
