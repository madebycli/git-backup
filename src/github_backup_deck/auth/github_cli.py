from __future__ import annotations

import json
import shutil
from dataclasses import dataclass

from github_backup_deck.process import CommandError, run_command


@dataclass(frozen=True, slots=True)
class AuthStatus:
    installed: bool
    authenticated: bool
    login: str | None = None
    error: str | None = None


class GitHubCliAuth:
    def status(self) -> AuthStatus:
        if shutil.which("gh") is None:
            return AuthStatus(False, False, error="GitHub CLI (gh) is not installed")
        result = run_command(
            ["gh", "auth", "status", "--hostname", "github.com"],
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return AuthStatus(True, False, error=result.stderr.strip() or "not authenticated")
        login_result = run_command(
            ["gh", "api", "user", "--jq", ".login"], timeout=30, check=False
        )
        login = login_result.stdout.strip() if login_result.returncode == 0 else None
        return AuthStatus(True, True, login=login or None)

    def login(self) -> AuthStatus:
        run_command(
            [
                "gh",
                "auth",
                "login",
                "--hostname",
                "github.com",
                "--web",
                "--git-protocol",
                "https",
            ],
            timeout=900,
        )
        run_command(["gh", "auth", "setup-git", "--hostname", "github.com"], timeout=60)
        return self.status()

    def diagnostics(self) -> dict[str, object]:
        status = self.status()
        return {
            "gh_installed": status.installed,
            "authenticated": status.authenticated,
            "login": status.login,
            "error": status.error,
        }

    def token_scopes(self) -> list[str]:
        try:
            result = run_command(
                ["gh", "auth", "status", "--hostname", "github.com", "--json", "tokenScopes"],
                timeout=30,
            )
            payload = json.loads(result.stdout)
            scopes = payload.get("tokenScopes", []) if isinstance(payload, dict) else []
            return [str(item) for item in scopes]
        except (CommandError, json.JSONDecodeError, RuntimeError):
            return []
