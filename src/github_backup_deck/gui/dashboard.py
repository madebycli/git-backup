from __future__ import annotations

from typing import Any


def build_dashboard(Gtk: Any) -> tuple[Any, Any, Any, Any, Any, Any]:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.get_style_context().add_class("card")
    title = Gtk.Label(label="Backup")
    title.set_xalign(0)
    title.get_style_context().add_class("title")
    box.pack_start(title, False, False, 0)
    destination = Gtk.Label(label="Destination: not selected")
    destination.set_xalign(0)
    destination.set_selectable(True)
    box.pack_start(destination, False, False, 0)
    progress = Gtk.ProgressBar()
    progress.set_show_text(True)
    box.pack_start(progress, False, False, 0)
    status = Gtk.Label(label="Ready")
    status.set_xalign(0)
    status.set_line_wrap(True)
    box.pack_start(status, False, False, 0)
    actions = Gtk.Box(spacing=8)
    probe = Gtk.Button(label="Probe")
    backup = Gtk.Button(label="Start backup")
    backup.get_style_context().add_class("suggested-action")
    actions.pack_start(probe, False, False, 0)
    actions.pack_start(backup, False, False, 0)
    box.pack_start(actions, False, False, 0)
    return box, destination, progress, status, probe, backup
