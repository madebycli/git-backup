from __future__ import annotations

from pathlib import Path
from typing import Any

from github_backup_deck.backup.runner import BackupRunner
from github_backup_deck.models import BackupPlan, Repository
from github_backup_deck.state import StateStore


class FakeMirror:
    def sync(
        self,
        repository: Repository,
        workspace: Path,
        *,
        fetch_lfs: bool = True,
        cancel_event: object | None = None,
    ) -> Path:
        path = workspace / "mirrors" / f"{repository.full_name}.git"
        path.mkdir(parents=True)
        (path / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        return path


class FakeMetadata:
    def write(
        self,
        repository: Repository,
        workspace: Path,
        options: object,
        *,
        cancel_event: object | None = None,
    ) -> Path:
        path = workspace / "metadata" / repository.full_name
        path.mkdir(parents=True)
        (path / "repository.json").write_text(
            f'{{"full_name":"{repository.full_name}"}}\n',
            encoding="utf-8",
        )
        return path


def test_runner_records_published_summary(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import github_backup_deck.backup.runner as runner_module

    monkeypatch.setattr(runner_module, "verify_mirror", lambda *_args, **_kwargs: None)
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
    assert summary.snapshot_path is not None
    assert state.latest_summary() is not None
