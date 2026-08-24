from __future__ import annotations

from collections.abc import Mapping

_GITHUB_CREDENTIAL_HELPER = "credential.https://github.com.helper"


def github_git_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Append a runtime gh credential helper after any existing Git config entries."""
    result = dict(environment)
    try:
        offset = int(result.get("GIT_CONFIG_COUNT", "0"))
    except ValueError:
        offset = 0

    # An empty helper resets helpers inherited from global/system Git config.
    # The following helper resolves `gh` through the current PATH instead of
    # persisting a Nix store path that may disappear after upgrades or GC.
    result[f"GIT_CONFIG_KEY_{offset}"] = _GITHUB_CREDENTIAL_HELPER
    result[f"GIT_CONFIG_VALUE_{offset}"] = ""
    result[f"GIT_CONFIG_KEY_{offset + 1}"] = _GITHUB_CREDENTIAL_HELPER
    result[f"GIT_CONFIG_VALUE_{offset + 1}"] = "!gh auth git-credential"
    result["GIT_CONFIG_COUNT"] = str(offset + 2)
    return result
