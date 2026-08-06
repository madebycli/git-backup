from __future__ import annotations

from pathlib import Path

from github_backup_deck.backup.runner import BackupRunner
from github_backup_deck.models import BackupPlan, Repository
from github_backup_deck.state import StateStore


class FakeMirror:
    def sync(self, repository: Repository, destination: Path, *, fetch_lfs: bool = True) -> Path:
        path = destination / "repositories" / f"{repository.full_name}.git"
        path.mkdir(parents=True)
        return path


class FakeMetadata:
    def write(self, repository: Repository, destination: Path, options: object) -> Path:
        path = destination / "metadata" / repository.full_name
        path.mkdir(parents=True)
        (path / "repository.json").write_text("{}\n")
        return path


def test_runner_records_summary(tmp_path: Path) -> None:
    repository = Repository(
        name="demo",
        full_name="owner/demo",
        clone_url="https://github.com/owner/demo.git",
    )
    state = StateStore(tmp_path / "state.sqlite3")
    runner = BackupRunner(
        mirror=FakeMirror(),  # type: ignore[arg-type]
        metadata=FakeMetadata(),  # type: ignore[arg-type]
        state=state,
    )
    summary = runner.run(BackupPlan(tmp_path / "backup", (repository,)))
    assert summary.repositories_ok == 1
    assert summary.repositories_failed == 0
    assert state.latest_summary() is not None
