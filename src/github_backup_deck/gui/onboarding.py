from __future__ import annotations

from typing import Any


def build_onboarding(Gtk: Any, on_login: Any, on_choose: Any) -> Any:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.get_style_context().add_class("card")
    title = Gtk.Label(label="Setup")
    title.set_xalign(0)
    title.get_style_context().add_class("title")
    box.pack_start(title, False, False, 0)
    text = Gtk.Label(
        label="Sign in with GitHub CLI, then choose a writable backup destination."
    )
    text.set_xalign(0)
    text.set_line_wrap(True)
    box.pack_start(text, False, False, 0)
    row = Gtk.Box(spacing=8)
    login = Gtk.Button(label="Sign in with GitHub")
    login.connect("clicked", on_login)
    choose = Gtk.Button(label="Choose folder")
    choose.connect("clicked", on_choose)
    row.pack_start(login, False, False, 0)
    row.pack_start(choose, False, False, 0)
    box.pack_start(row, False, False, 0)
    return box
