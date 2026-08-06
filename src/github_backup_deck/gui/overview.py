from __future__ import annotations

from typing import Any

from github_backup_deck.state import StateStore


def _summary_text(summary: dict[str, Any] | None) -> str:
    if summary is None:
        return "No completed backup has been recorded yet."
    return (
        f"Last backup: {summary.get('finished_at', 'unknown')}\n"
        f"Destination: {summary.get('destination', 'unknown')}\n"
        f"Repositories: {summary.get('repositories_ok', 0)} successful, "
        f"{summary.get('repositories_failed', 0)} failed"
    )


def main() -> int:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, Gtk, GtkLayerShell

    window = Gtk.Window(title="GitHub Backup Overview")
    window.set_default_size(560, 240)
    window.set_border_width(24)
    GtkLayerShell.init_for_window(window)
    GtkLayerShell.set_namespace(window, "github-backup-deck-overview")
    GtkLayerShell.set_layer(window, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_exclusive_zone(window, 0)
    GtkLayerShell.set_keyboard_mode(window, GtkLayerShell.KeyboardMode.ON_DEMAND)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    title = Gtk.Label(label="GitHub Backup Overview")
    title.set_xalign(0)
    title.set_markup("<span size='x-large' weight='bold'>GitHub Backup Overview</span>")
    box.pack_start(title, False, False, 0)
    summary = StateStore().latest_summary()
    label = Gtk.Label(label=_summary_text(summary))
    label.set_xalign(0)
    label.set_line_wrap(True)
    label.set_selectable(True)
    box.pack_start(label, True, True, 0)
    close = Gtk.Button(label="Close")
    close.connect("clicked", lambda _button: Gtk.main_quit())
    box.pack_end(close, False, False, 0)
    window.add(box)

    def key_press(_widget: Any, event: Any) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            Gtk.main_quit()
            return True
        return False

    window.connect("key-press-event", key_press)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
