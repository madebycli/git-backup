from __future__ import annotations

import threading
from pathlib import Path

from github_backup_deck.process import run_command


def has_refs(
    mirror: Path,
    *,
    cancel_event: threading.Event | None = None,
) -> bool:
    """Return whether a bare mirror contains at least one Git ref.

    Empty GitHub repositories legitimately have an unborn symbolic HEAD and no
    entries below refs/. Commands such as ``git lfs fetch --all`` must not be
    asked to resolve HEAD in that state.
    """

    result = run_command(
        [
            "git",
            "-C",
            str(mirror),
            "for-each-ref",
            "--count=1",
            "--format=%(refname)",
            "refs/",
        ],
        timeout=60,
        cancel_event=cancel_event,
    )
    return bool(result.stdout.strip())


def has_resolvable_head(
    mirror: Path,
    *,
    cancel_event: threading.Event | None = None,
) -> bool:
    """Return whether HEAD resolves to a commit without emitting an error."""

    result = run_command(
        [
            "git",
            "-C",
            str(mirror),
            "rev-parse",
            "--verify",
            "--quiet",
            "HEAD^{commit}",
        ],
        timeout=60,
        cancel_event=cancel_event,
        check=False,
    )
    return result.returncode == 0
