from __future__ import annotations

from pathlib import Path
from typing import Any


def choose_storage(parent: Any, current: Path) -> Path | None:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gtk, GtkLayerShell

    dialog = Gtk.FileChooserNative.new(
        "Choose backup folder",
        parent,
        Gtk.FileChooserAction.SELECT_FOLDER,
        "Choose",
        "Cancel",
    )
    dialog.set_modal(True)
    if current.exists():
        dialog.set_current_folder(str(current))
    parent.set_sensitive(False)
    try:
        GtkLayerShell.set_keyboard_mode(parent, GtkLayerShell.KeyboardMode.ON_DEMAND)
        response = dialog.run()
        filename = dialog.get_filename() if response == Gtk.ResponseType.ACCEPT else None
    finally:
        dialog.destroy()
        GtkLayerShell.set_keyboard_mode(parent, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        parent.set_sensitive(True)
        parent.present()
    return Path(filename) if filename else None
