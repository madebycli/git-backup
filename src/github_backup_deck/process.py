from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from github_backup_deck.backup.git_auth import github_git_environment


@dataclass(frozen=True, slots=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandError(RuntimeError):
    def __init__(self, result: CommandResult) -> None:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        super().__init__(f"{result.args[0]} exited with {result.returncode}: {detail}")
        self.result = result


class CommandCancelled(RuntimeError):
    pass


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait(timeout=5)


def run_command(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = 300.0,
    check: bool = True,
    env: Mapping[str, str] | None = None,
    cancel_event: threading.Event | None = None,
) -> CommandResult:
    if not args:
        raise ValueError("args must not be empty")
    merged_env = os.environ.copy()
    merged_env.setdefault("GIT_TERMINAL_PROMPT", "0")
    if env:
        merged_env.update(env)
    if args[0] == "git":
        merged_env = github_git_environment(merged_env)
    process = subprocess.Popen(
        list(args),
        cwd=cwd,
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout
    stdout = ""
    stderr = ""
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                _terminate_process(process)
                raise CommandCancelled(f"Command cancelled: {args[0]}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate_process(process)
                raise RuntimeError(f"Command timed out after {timeout:.0f}s: {args[0]}")
            try:
                output_stdout, output_stderr = process.communicate(
                    timeout=min(0.25, remaining)
                )
                stdout = output_stdout or ""
                stderr = output_stderr or ""
                break
            except subprocess.TimeoutExpired:
                continue
    except BaseException:
        _terminate_process(process)
        raise
    returncode = process.returncode
    if returncode is None:
        raise RuntimeError(f"Command did not terminate: {args[0]}")
    result = CommandResult(tuple(args), returncode, stdout, stderr)
    if check and result.returncode != 0:
        raise CommandError(result)
    return result
