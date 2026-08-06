from github_backup_deck.auth.github_cli import _clean_output, _extract_device_code


def test_extract_device_code_from_gh_output() -> None:
    assert _extract_device_code("copy A521-E4FC now") == "A521-E4FC"


def test_clean_output_removes_ansi_sequences() -> None:
    assert _clean_output("\x1b[32mAuthentication complete\x1b[0m\n") == "Authentication complete"
