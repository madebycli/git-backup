from __future__ import annotations

from pathlib import Path
from typing import Any


def choose_storage(parent: Any, current: Path) -> Path | None:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk

    dialog = Gtk.FileChooserDialog(
        title="Choose backup folder",
        transient_for=parent,
        action=Gtk.FileChooserAction.SELECT_FOLDER,
    )
    dialog.add_buttons(
        "Cancel",
        Gtk.ResponseType.CANCEL,
        "Choose",
        Gtk.ResponseType.OK,
    )
    if current.exists():
        dialog.set_current_folder(str(current))
    response = dialog.run()
    selected = Path(dialog.get_filename()) if response == Gtk.ResponseType.OK else None
    dialog.destroy()
    return selected
