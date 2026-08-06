from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

from github_backup_deck.app import BackupApplication
from github_backup_deck.auth.github_cli import GitHubCliAuth
from github_backup_deck.config import ConfigStore
from github_backup_deck.events import ProgressEvent
from github_backup_deck.gui.dashboard import build_dashboard
from github_backup_deck.gui.login_dialog import run_login
from github_backup_deck.gui.onboarding import build_onboarding
from github_backup_deck.gui.storage_dialog import choose_storage
from github_backup_deck.storage.probe import probe_path


def _load_gtk() -> tuple[Any, Any, Any]:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gio, GLib, Gtk

    return Gtk, GLib, Gio


def _apply_wayland_app_id(window: Any) -> None:
    def on_realize(widget: Any) -> None:
        gdk_window = widget.get_window()
        if gdk_window is not None and hasattr(gdk_window, "set_application_id"):
            gdk_window.set_application_id("github-backup-deck")

    window.connect("realize", on_realize)


def run_gui() -> int:
    Gtk, GLib, Gio = _load_gtk()

    class MainWindow(Gtk.ApplicationWindow):
        def __init__(self, application: Any) -> None:
            super().__init__(application=application, title="GitHub Backup Deck")
            self.set_default_size(960, 640)
            self.set_border_width(24)
            _apply_wayland_app_id(self)
            self.config_store = ConfigStore()
            self.config = self.config_store.load()
            self.backup_app = BackupApplication(config=self.config_store)
            self.auth = GitHubCliAuth()
            self._busy = False

            provider = Gtk.CssProvider()
            css_path = Path(__file__).with_name("style.css")
            provider.load_from_path(str(css_path))
            Gtk.StyleContext.add_provider_for_screen(
                self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            header = Gtk.Label(label="GitHub Backup Deck")
            header.set_xalign(0)
            header.get_style_context().add_class("title")
            root.pack_start(header, False, False, 0)
            subtitle = Gtk.Label(
                label="Mirror repositories and preserve GitHub metadata without managing a token."
            )
            subtitle.set_xalign(0)
            subtitle.get_style_context().add_class("subtitle")
            root.pack_start(subtitle, False, False, 0)
            root.pack_start(
                build_onboarding(Gtk, self._login_clicked, self._choose_clicked),
                False,
                False,
                0,
            )
            (
                dashboard,
                self.destination_label,
                self.progress,
                self.status_label,
                self.probe_button,
                self.backup_button,
            ) = build_dashboard(Gtk)
            self.probe_button.connect("clicked", self._probe_clicked)
            self.backup_button.connect("clicked", self._backup_clicked)
            root.pack_start(dashboard, True, True, 0)
            self.add(root)
            self._refresh()

        def _refresh(self) -> None:
            auth = self.auth.status()
            login = auth.login or "not signed in"
            self.destination_label.set_text(
                f"Account: {login}\nDestination: {self.config.backup_path}"
            )

        def _login_clicked(self, _button: Any) -> None:
            if run_login(self):
                self.status_label.set_text("GitHub login succeeded")
            else:
                self.status_label.set_text("GitHub login was not completed")
            self._refresh()

        def _choose_clicked(self, _button: Any) -> None:
            selected = choose_storage(self, self.config.backup_path)
            if selected is None:
                return
            self.config = replace(self.config, default_backup_directory=str(selected))
            self.config_store.save(self.config)
            self.status_label.set_text("Backup destination saved")
            self._refresh()

        def _probe_clicked(self, _button: Any) -> None:
            result = probe_path(self.config.backup_path)
            free_gib = result.free_bytes / (1024**3)
            if result.ok:
                self.status_label.set_text(
                    f"Storage probe succeeded. {free_gib:.1f} GiB available."
                )
            else:
                self.status_label.set_text(f"Storage probe failed: {result.error}")

        def _backup_clicked(self, _button: Any) -> None:
            if self._busy:
                return
            self._busy = True
            self.backup_button.set_sensitive(False)
            self.progress.set_fraction(0.0)
            self.status_label.set_text("Preparing backup…")

            def worker() -> None:
                try:
                    summary = self.backup_app.backup(
                        self.config.backup_path,
                        sink=lambda event: GLib.idle_add(self._show_event, event),
                    )
                    GLib.idle_add(self._backup_done, summary.repositories_failed)
                except Exception as exc:  # noqa: BLE001 - UI boundary
                    GLib.idle_add(self._backup_failed, str(exc))

            threading.Thread(target=worker, name="github-backup", daemon=True).start()

        def _show_event(self, event: ProgressEvent) -> bool:
            if event.current is not None and event.total:
                self.progress.set_fraction(event.current / event.total)
                self.progress.set_text(f"{event.current}/{event.total}")
            self.status_label.set_text(event.message)
            return False

        def _backup_done(self, failures: int) -> bool:
            self._busy = False
            self.backup_button.set_sensitive(True)
            self.progress.set_fraction(1.0)
            self.status_label.set_text(
                "Backup completed"
                if failures == 0
                else f"Backup completed with {failures} failures"
            )
            return False

        def _backup_failed(self, error: str) -> bool:
            self._busy = False
            self.backup_button.set_sensitive(True)
            self.status_label.set_text(f"Backup failed: {error}")
            return False

    class Application(Gtk.Application):
        def __init__(self) -> None:
            super().__init__(
                application_id="com.madebycli.GitHubBackupDeck",
                flags=Gio.ApplicationFlags.FLAGS_NONE,
            )

        def do_activate(self) -> None:
            window = self.props.active_window or MainWindow(self)
            window.show_all()
            window.present()

    return int(Application().run([]))


def main() -> int:
    return run_gui()
