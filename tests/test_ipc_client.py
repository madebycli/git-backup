from __future__ import annotations

from pathlib import Path

from github_backup_deck import __version__
from github_backup_deck.ipc.client import IpcClient, daemon_is_compatible, daemon_job_is_active


def test_daemon_compatibility_requires_exact_runtime_version() -> None:
    assert daemon_is_compatible(
        {"ok": True, "protocol": 3, "version": __version__}
    )
    assert not daemon_is_compatible({"ok": True, "protocol": 3})
    assert not daemon_is_compatible(
        {"ok": True, "protocol": 3, "version": "0.3.8"}
    )
    assert not daemon_is_compatible(
        {"ok": True, "protocol": 2, "version": __version__}
    )


def test_active_job_detection_preserves_running_previous_daemon() -> None:
    assert daemon_job_is_active({"job": {"state": "running"}})
    assert daemon_job_is_active({"job": {"state": "cancelling"}})
    assert not daemon_job_is_active({"job": {"state": "completed"}})
    assert not daemon_job_is_active(None)


def test_previous_daemon_is_kept_while_backup_is_active(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = IpcClient(tmp_path / "control.sock")
    old = {"ok": True, "protocol": 3, "version": "0.3.8", "pid": 4242}
    monkeypatch.setattr(client, "_probe", lambda: (old, 4242))
    monkeypatch.setattr(
        client,
        "_status",
        lambda: {"ok": True, "job": {"state": "running"}},
    )

    retired: list[int | None] = []
    monkeypatch.setattr(
        client,
        "_retire_stale_daemon",
        lambda pid, _response: retired.append(pid),
    )

    client.ensure_server(timeout=0.1)
    assert retired == []


def test_completed_previous_daemon_is_retired_before_new_server(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = IpcClient(tmp_path / "control.sock")
    old = {"ok": True, "protocol": 3, "version": "0.3.8", "pid": 4242}
    current = {"ok": True, "protocol": 3, "version": __version__, "pid": 4343}
    probes = iter([(old, 4242), (old, 4242), (current, 4343)])
    monkeypatch.setattr(client, "_probe", lambda: next(probes))
    monkeypatch.setattr(
        client,
        "_status",
        lambda: {"ok": True, "job": {"state": "completed"}},
    )

    retired: list[int | None] = []
    monkeypatch.setattr(
        client,
        "_retire_stale_daemon",
        lambda pid, _response: retired.append(pid),
    )
    monkeypatch.setattr(
        "github_backup_deck.ipc.client.shutil.which",
        lambda _name: "/usr/bin/github-backup-deck-daemon",
    )

    class FakeProcess:
        pass

    monkeypatch.setattr(
        "github_backup_deck.ipc.client.subprocess.Popen",
        lambda *_args, **_kwargs: FakeProcess(),
    )

    client.ensure_server(timeout=0.5)
    assert retired == [4242]
