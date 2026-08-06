from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


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


def run_command(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float = 300.0,
    check: bool = True,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    if not args:
        raise ValueError("args must not be empty")
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Command timed out after {timeout:.0f}s: {args[0]}") from exc
    result = CommandResult(tuple(args), completed.returncode, completed.stdout, completed.stderr)
    if check and result.returncode != 0:
        raise CommandError(result)
    return result
