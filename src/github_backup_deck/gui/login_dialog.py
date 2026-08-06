from __future__ import annotations

from typing import Any

from github_backup_deck.auth.github_cli import GitHubCliAuth


def run_login(parent: Any) -> bool:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK_CANCEL,
        text="Sign in to GitHub",
    )
    dialog.format_secondary_text(
        "GitHub CLI opens a browser and stores credentials in its own secure configuration."
    )
    accepted = dialog.run() == Gtk.ResponseType.OK
    dialog.destroy()
    if not accepted:
        return False
    try:
        status = GitHubCliAuth().login()
        return status.authenticated
    except RuntimeError as exc:
        error = Gtk.MessageDialog(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="GitHub login failed",
        )
        error.format_secondary_text(str(exc))
        error.run()
        error.destroy()
        return False
