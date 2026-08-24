from __future__ import annotations

from github_backup_deck.backup.git_auth import github_git_environment


def test_runtime_helper_resets_stale_github_credential_helper() -> None:
    environment = {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "credential.https://github.com.helper",
        "GIT_CONFIG_VALUE_0": "!/nix/store/gone-gh/bin/.gh-wrapped auth git-credential",
    }

    result = github_git_environment(environment)

    assert result["GIT_CONFIG_COUNT"] == "3"
    assert result["GIT_CONFIG_VALUE_0"].startswith("!/nix/store/gone-gh/")
    assert result["GIT_CONFIG_KEY_1"] == "credential.https://github.com.helper"
    assert result["GIT_CONFIG_VALUE_1"] == ""
    assert result["GIT_CONFIG_KEY_2"] == "credential.https://github.com.helper"
    assert result["GIT_CONFIG_VALUE_2"] == "!gh auth git-credential"
