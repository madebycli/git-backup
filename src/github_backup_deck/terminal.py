from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TerminalLauncher:
    name: str
    prefix: tuple[str, ...]


_LAUNCHERS = (
    TerminalLauncher("Ghostty", ("ghostty", "-e")),
    TerminalLauncher("kitty", ("kitty", "--detach")),
    TerminalLauncher("foot", ("foot", "-e")),
    TerminalLauncher("Alacritty", ("alacritty", "-e")),
    TerminalLauncher("Konsole", ("konsole", "-e")),
    TerminalLauncher("GNOME Terminal", ("gnome-terminal", "--")),
    TerminalLauncher("xterm", ("xterm", "-e")),
)


def find_login_terminal(
    executable: str = "github-backup-deck",
) -> tuple[TerminalLauncher, list[str]] | None:
    program = shutil.which(executable) or executable
    for launcher in _LAUNCHERS:
        resolved = shutil.which(launcher.prefix[0])
        if resolved is None:
            continue
        return launcher, [resolved, *launcher.prefix[1:], program, "login"]
    return None


def launch_login_terminal(executable: str = "github-backup-deck") -> str:
    detected = find_login_terminal(executable)
    if detected is None:
        raise RuntimeError(
            "No supported terminal found. Install Ghostty, kitty, foot, "
            "Alacritty, Konsole, GNOME Terminal or xterm."
        )
    launcher, command = detected
    subprocess.Popen(  # noqa: S603 - fixed executable selected with shutil.which
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return launcher.name
