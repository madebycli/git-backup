from github_backup_deck.terminal import find_login_terminal


def test_terminal_command_uses_login_subcommand(monkeypatch) -> None:
    monkeypatch.setattr(
        "shutil.which", lambda name: f"/bin/{name}" if name == "ghostty" else None
    )
    detected = find_login_terminal()
    assert detected is not None
    launcher, command = detected
    assert launcher.name == "Ghostty"
    assert command == ["/bin/ghostty", "-e", "github-backup-deck", "login"]
