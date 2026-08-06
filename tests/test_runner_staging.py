from __future__ import annotations

from pathlib import Path
from typing import Any

from github_backup_deck.backup.runner import BackupRunner
from github_backup_deck.models import BackupOptions, BackupPlan, Repository
from github_backup_deck.state import StateStore


class FakeMirror:
    def sync(self, repository: Repository, workspace: Path, **_kwargs: object) -> Path:
        path = workspace / "mirrors" / f"{repository.full_name}.git"
        path.mkdir(parents=True)
        (path / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        return path


class FakeMetadata:
    def write(
        self,
        repository: Repository,
        workspace: Path,
        _options: object,
        **_kwargs: object,
    ) -> Path:
        path = workspace / "metadata" / repository.full_name
        path.mkdir(parents=True)
        (path / "repository.json").write_text(
            f'{{"full_name":"{repository.full_name}"}}\n',
            encoding="utf-8",
        )
        return path


def _repo() -> Repository:
    return Repository("demo", "owner/demo", "https://example.invalid/owner/demo.git")


def _runner(tmp_path: Path) -> BackupRunner:
    return BackupRunner(
        mirror=FakeMirror(),  # type: ignore[arg-type]
        metadata=FakeMetadata(),  # type: ignore[arg-type]
        state=StateStore(tmp_path / "state.sqlite3"),
    )


def test_zip_run_publishes_only_zip_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import github_backup_deck.backup.runner as runner_module

    monkeypatch.setattr(runner_module, "verify_mirror", lambda *_args, **_kwargs: None)
    destination = tmp_path / "GitHub Backup"
    summary = _runner(tmp_path).run(
        BackupPlan(destination, (_repo(),), BackupOptions(backup_format="zip"))
    )
    final = Path(summary.snapshot_path or "")
    assert (final / "repositories" / "owner" / "demo.zip").is_file()
    assert not (final / "repositories" / "owner" / "demo").exists()
    assert not (tmp_path / ".GitHub Backup.github-backup-deck-staging").exists()
    assert not (destination / "repositories").exists()
    assert not (destination / "metadata").exists()


def test_folder_run_publishes_only_folder(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    import github_backup_deck.backup.runner as runner_module

    monkeypatch.setattr(runner_module, "verify_mirror", lambda *_args, **_kwargs: None)
    destination = tmp_path / "GitHub Backup"
    summary = _runner(tmp_path).run(
        BackupPlan(destination, (_repo(),), BackupOptions(backup_format="folder"))
    )
    final = Path(summary.snapshot_path or "")
    head = final / "repositories" / "owner" / "demo" / "repository.git" / "HEAD"
    assert head.is_file()
    assert not (final / "repositories" / "owner" / "demo.zip").exists()
