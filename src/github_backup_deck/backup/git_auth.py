from __future__ import annotations

_GITHUB_CREDENTIAL_HELPER = "credential.https://github.com.helper"


def github_git_command(*args: str) -> list[str]:
    """Build a git command that ignores stale GitHub helpers and uses current gh."""
    return [
        "git",
        "-c",
        f"{_GITHUB_CREDENTIAL_HELPER}=",
        "-c",
        f"{_GITHUB_CREDENTIAL_HELPER}=!gh auth git-credential",
        *args,
    ]
