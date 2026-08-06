from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from github_backup_deck.app import BackupApplication
from github_backup_deck.auth.github_cli import GitHubCliAuth
from github_backup_deck.config import AppConfig, ConfigStore
from github_backup_deck.events import ProgressEvent
from github_backup_deck.gui.login_dialog import run_login
from github_backup_deck.gui.storage_dialog import choose_storage
from github_backup_deck.storage.probe import probe_path


def _gtk() -> tuple[Any, Any, Any, Any]:
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, GLib, Gtk, GtkLayerShell

    return Gtk, Gdk, GLib, GtkLayerShell


def run_gui() -> int:
    Gtk, Gdk, GLib, GtkLayerShell = _gtk()

    class Window(Gtk.Window):
        def __init__(self) -> None:
            super().__init__(type=Gtk.WindowType.TOPLEVEL)
            self.store = ConfigStore()
            self.config = self.store.load()
            self.app = BackupApplication(config=self.store)
            self.auth = GitHubCliAuth()
            self.busy = False
            self.scanning = False
            self.authenticated = False
            self.repositories: list[Any] = []
            self._window_setup()
            self._css()
            self._ui()
            self.connect("key-press-event", self._key)
            self.connect("destroy", lambda *_: Gtk.main_quit())
            self.show_all()
            GLib.idle_add(self._start)

        def _window_setup(self) -> None:
            self.set_title("GitHub Backup Deck")
            self.set_app_paintable(True)
            self.set_decorated(False)
            self.set_resizable(False)
            width, height = 8 * (124 + 44) + 72, 900
            display = Gdk.Display.get_default()
            if display is not None:
                monitor = display.get_primary_monitor()
                if monitor is None and display.get_n_monitors() > 0:
                    monitor = display.get_monitor(0)
                if monitor is not None:
                    geometry = monitor.get_geometry()
                    width = min(width, max(820, geometry.width - 120))
                    height = min(height, max(620, geometry.height - 160))
            self.set_size_request(width, height)
            rgba = self.get_screen().get_rgba_visual()
            if rgba is not None:
                self.set_visual(rgba)
            GtkLayerShell.init_for_window(self)
            GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
            GtkLayerShell.set_namespace(self, "github-backup-deck")
            GtkLayerShell.set_exclusive_zone(self, 0)

        def _css(self) -> None:
            provider = Gtk.CssProvider()
            provider.load_from_path(str(Path(__file__).with_name("style.css")))
            Gtk.StyleContext.add_provider_for_screen(
                self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        @staticmethod
        def _label(text: str, css: str, xalign: float = 0.0) -> Any:
            widget = Gtk.Label(label=text)
            widget.set_xalign(xalign)
            widget.get_style_context().add_class(css)
            return widget

        @staticmethod
        def _button(text: str, css: str, callback: Any) -> Any:
            widget = Gtk.Button(label=text)
            widget.get_style_context().add_class(css)
            widget.connect("clicked", callback)
            return widget

        @staticmethod
        def _margins(widget: Any, value: int) -> None:
            for side in ("top", "bottom", "start", "end"):
                getattr(widget, f"set_margin_{side}")(value)

        def _card(self, title: str) -> Any:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            box.get_style_context().add_class("deck-card")
            box.pack_start(self._label(title, "section-label"), False, False, 0)
            return box

        def _toggle(self, text: str, active: bool) -> Any:
            widget = Gtk.CheckButton(label=text)
            widget.set_mode(False)
            widget.set_active(active)
            widget.get_style_context().add_class("chip")
            return widget

        def _ui(self) -> None:
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            root.get_style_context().add_class("picker-root")
            root.pack_start(self._header(), False, False, 0)
            root.pack_start(Gtk.Separator(), False, False, 0)
            body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            self._margins(body, 14)
            cards = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            cards.set_homogeneous(True)
            cards.pack_start(self._account_card(), True, True, 0)
            cards.pack_start(self._destination_card(), True, True, 0)
            body.pack_start(cards, False, False, 0)
            body.pack_start(self._options(), False, False, 0)
            body.pack_start(self._progress(), False, False, 0)
            body.pack_start(self._log(), True, True, 0)
            body.pack_start(
                self._label(
                    "Esc = close  •  Ctrl+L = login  •  Ctrl+R = rescan  •  Ctrl+B = backup",
                    "picker-hint",
                    0.5,
                ),
                False,
                False,
                0,
            )
            root.pack_start(body, True, True, 0)
            self.add(root)

        def _header(self) -> Any:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            self._margins(box, 14)
            box.pack_start(self._button("✕", "x-btn", lambda *_: self._close()), False, False, 0)
            titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            titles.pack_start(self._label("GitHub Backup Deck", "picker-title"), False, False, 0)
            titles.pack_start(
                self._label(
                    "Versioned mirrors · GitHub metadata · GIF Picker family", "picker-hint"
                ),
                False,
                False,
                0,
            )
            box.pack_start(titles, True, True, 0)
            self.head = self._label("READY", "status-chip")
            box.pack_end(self.head, False, False, 0)
            return box

        def _account_card(self) -> Any:
            card = self._card("GITHUB ACCOUNT")
            self.account = self._label("Not signed in", "card-title")
            self.repo_count = self._label("Repository scan waiting", "card-detail")
            card.pack_start(self.account, False, False, 0)
            card.pack_start(self.repo_count, False, False, 0)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.login = self._button("Sign in", "action-btn", self._login)
            self.scan = self._button("Scan repositories", "chip", lambda *_: self._scan())
            row.pack_start(self.login, False, False, 0)
            row.pack_start(self.scan, False, False, 0)
            card.pack_end(row, False, False, 0)
            return card

        def _destination_card(self) -> Any:
            card = self._card("BACKUP DESTINATION")
            self.destination = self._label(str(self.config.backup_path), "card-title")
            self.destination.set_line_wrap(True)
            self.storage = self._label("Storage not probed", "card-detail")
            card.pack_start(self.destination, False, False, 0)
            card.pack_start(self.storage, False, False, 0)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            choose = self._button("Choose folder", "action-btn", self._choose)
            row.pack_start(choose, False, False, 0)
            row.pack_start(self._button("Probe", "chip", lambda *_: self._probe()), False, False, 0)
            card.pack_end(row, False, False, 0)
            return card

        def _options(self) -> Any:
            card = self._card("BACKUP CONTENT · ALL ACCESSIBLE REPOSITORIES · EVERY GIT REF")
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.issues = self._toggle("Issues", self.config.include_issues)
            self.pulls = self._toggle("Pull requests", self.config.include_pull_requests)
            self.releases = self._toggle("Releases", self.config.include_releases)
            self.archived = self._toggle("Archived repos", self.config.include_archived)
            self.lfs = self._toggle("Git LFS", self.config.fetch_lfs)
            for widget in (self.issues, self.pulls, self.releases, self.archived, self.lfs):
                row.pack_start(widget, False, False, 0)
            card.pack_start(row, False, False, 0)
            formats = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            formats.pack_start(self._label("Snapshot format", "card-detail"), False, False, 0)
            self.zip = Gtk.RadioButton.new_with_label_from_widget(None, "ZIP per repository")
            self.folder = Gtk.RadioButton.new_with_label_from_widget(
                self.zip, "Folder per repository"
            )
            for widget in (self.zip, self.folder):
                widget.set_mode(False)
                widget.get_style_context().add_class("chip")
                formats.pack_start(widget, False, False, 0)
            self.zip.set_active(self.config.backup_format == "zip")
            self.folder.set_active(self.config.backup_format == "folder")
            self.versioned = self._toggle("Versioned snapshots", self.config.versioned_snapshots)
            formats.pack_start(self.versioned, False, False, 0)
            card.pack_start(formats, False, False, 0)
            return card

        def _progress(self) -> Any:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.status = self._label("Ready", "card-detail")
            self.backup = self._button("Start backup", "primary-btn", self._backup)
            row.pack_start(self.status, True, True, 0)
            row.pack_end(self.backup, False, False, 0)
            self.bar = Gtk.ProgressBar()
            self.bar.set_show_text(True)
            self.bar.set_text("Waiting")
            self.bar.get_style_context().add_class("deck-progress")
            box.pack_start(row, False, False, 0)
            box.pack_start(self.bar, False, False, 0)
            return box

        def _log(self) -> Any:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            row.pack_start(self._label("LIVE LOG", "section-label"), False, False, 0)
            row.pack_end(
                self._button("Clear", "chip", lambda *_: self.log_buffer.set_text("")),
                False,
                False,
                0,
            )
            scroll = Gtk.ScrolledWindow()
            scroll.get_style_context().add_class("log-scroll")
            self.log = Gtk.TextView()
            self.log.set_editable(False)
            self.log.set_cursor_visible(False)
            self.log.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            for side in ("left", "right", "top", "bottom"):
                getattr(self.log, f"set_{side}_margin")(10)
            self.log.get_style_context().add_class("log-view")
            self.log_buffer = self.log.get_buffer()
            scroll.add(self.log)
            box.pack_start(row, False, False, 0)
            box.pack_start(scroll, True, True, 0)
            return box

        def _start(self) -> bool:
            self._probe()
            self._line("info", "Opened in GIF Picker layer-shell mode")
            self._scan()
            return False

        def _login(self, _button: Any) -> None:
            if self.busy:
                return
            self._line("info", "Starting GitHub browser login")
            if run_login(self):
                self.authenticated = True
                self._line("success", "GitHub login completed")
                self._scan()
            else:
                self._line("warning", "GitHub login cancelled or incomplete")

        def _choose(self, _button: Any) -> None:
            if self.busy:
                return
            selected = choose_storage(self, self.config.backup_path)
            if selected is None:
                return
            self.config = replace(self.config, default_backup_directory=str(selected))
            self.store.save(self.config)
            self.destination.set_text(str(selected))
            self._line("info", f"Destination changed to {selected}")
            self._probe()

        def _probe(self) -> None:
            result = probe_path(self.config.backup_path)
            if result.ok:
                self.storage.set_text(f"Writable · {result.free_bytes / (1024**3):.1f} GiB free")
            else:
                self.storage.set_text(result.error or "Storage probe failed")

        def _scan(self) -> None:
            if self.scanning or self.busy:
                return
            self.scanning = True
            self.scan.set_sensitive(False)
            self.repo_count.set_text("Checking GitHub session…")
            self.head.set_text("SCANNING")
            include_archived = self.archived.get_active()

            def worker() -> None:
                try:
                    session = self.auth.status()
                    repositories: list[Any] = []
                    if session.authenticated:
                        repositories = self.app.planner.repositories.list_accessible(
                            include_archived=include_archived
                        )
                    GLib.idle_add(self._scan_done, session, repositories, None)
                except Exception as exc:  # noqa: BLE001
                    GLib.idle_add(self._scan_done, None, [], str(exc))

            threading.Thread(target=worker, name="github-scan", daemon=True).start()

        def _scan_done(self, session: Any, repositories: list[Any], error: str | None) -> bool:
            self.scanning = False
            self.scan.set_sensitive(True)
            if error:
                self.head.set_text("ERROR")
                self.repo_count.set_text("Repository scan failed")
                self._line("error", error)
                return False
            self.authenticated = bool(session and session.authenticated)
            if not self.authenticated:
                self.account.set_text("Not signed in")
                self.login.set_label("Sign in")
                self.repo_count.set_text("Sign in to scan repositories")
                self.head.set_text("LOGIN REQUIRED")
                return False
            self.account.set_text(session.login or "Signed in")
            self.login.set_label("Switch account")
            self.repositories = repositories
            private = sum(bool(repo.private) for repo in repositories)
            archived = sum(bool(repo.archived) for repo in repositories)
            public = len(repositories) - private
            self.repo_count.set_text(
                f"{len(repositories)} repos · {private} private · {public} public · "
                f"{archived} archived"
            )
            self.head.set_text(f"{len(repositories)} REPOS")
            self._line("success", f"Found {len(repositories)} accessible repositories")
            return False

        def _save(self) -> AppConfig:
            self.config = replace(
                self.config,
                include_issues=self.issues.get_active(),
                include_pull_requests=self.pulls.get_active(),
                include_releases=self.releases.get_active(),
                include_archived=self.archived.get_active(),
                fetch_lfs=self.lfs.get_active(),
                backup_format="zip" if self.zip.get_active() else "folder",
                versioned_snapshots=self.versioned.get_active(),
            )
            self.store.save(self.config)
            return self.config

        def _backup(self, _button: Any) -> None:
            if self.busy:
                return
            if not self.authenticated:
                self._login(self.login)
                return
            config = self._save()
            probe = probe_path(config.backup_path)
            if not probe.ok:
                self._line("error", probe.error or "Destination is not writable")
                return
            self.busy = True
            for widget in (self.backup, self.login, self.scan):
                widget.set_sensitive(False)
            self.bar.set_fraction(0)
            self.bar.set_text("Preparing…")
            self.status.set_text("Preparing versioned backup…")
            self.head.set_text("BACKING UP")
            self._line(
                "info",
                f"Start: {config.backup_path} · {config.backup_format} · "
                f"versioned={config.versioned_snapshots}",
            )

            def worker() -> None:
                try:
                    summary = self.app.backup(
                        config.backup_path,
                        sink=lambda event: GLib.idle_add(self._event, event),
                    )
                    GLib.idle_add(self._done, summary)
                except Exception as exc:  # noqa: BLE001
                    GLib.idle_add(self._failed, str(exc))

            threading.Thread(target=worker, name="github-backup", daemon=True).start()

        def _event(self, event: ProgressEvent) -> bool:
            if event.current is not None and event.total:
                self.bar.set_fraction(event.current / event.total)
                self.bar.set_text(f"{event.current}/{event.total} repositories")
            self.status.set_text(event.message)
            message = f"{event.repository}: {event.message}" if event.repository else event.message
            self._line(event.kind, message)
            return False

        def _done(self, summary: Any) -> bool:
            self._unlock()
            self.bar.set_fraction(1)
            self.bar.set_text(f"{summary.repositories_ok}/{summary.repositories_total} complete")
            self.head.set_text("COMPLETE" if not summary.repositories_failed else "WARNING")
            self.status.set_text(
                "Backup completed"
                if not summary.repositories_failed
                else f"Completed with {summary.repositories_failed} failures"
            )
            if summary.snapshot_path:
                self._line("success", f"Snapshot: {summary.snapshot_path}")
            return False

        def _failed(self, error: str) -> bool:
            self._unlock()
            self.head.set_text("ERROR")
            self.status.set_text(f"Backup failed: {error}")
            self.bar.set_text("Failed")
            self._line("error", error)
            return False

        def _unlock(self) -> None:
            self.busy = False
            for widget in (self.backup, self.login, self.scan):
                widget.set_sensitive(True)

        def _line(self, kind: str, message: str) -> None:
            marker = {"success": "✓", "warning": "!", "error": "×", "progress": "→"}.get(
                kind, "·"
            )
            end = self.log_buffer.get_end_iter()
            self.log_buffer.insert(end, f"{datetime.now():%H:%M:%S}  {marker}  {message}\n")
            mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
            self.log.scroll_mark_onscreen(mark)
            self.log_buffer.delete_mark(mark)

        def _close(self) -> None:
            if self.busy:
                self._line("warning", "Backup is running; window stays open")
                return
            self.destroy()

        def _key(self, _widget: Any, event: Any) -> bool:
            if event.keyval == Gdk.KEY_Escape:
                self._close()
                return True
            control = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
            if control and event.keyval in (Gdk.KEY_l, Gdk.KEY_L):
                self._login(self.login)
                return True
            if control and event.keyval in (Gdk.KEY_r, Gdk.KEY_R):
                self._scan()
                return True
            if control and event.keyval in (Gdk.KEY_b, Gdk.KEY_B):
                self._backup(self.backup)
                return True
            return False

    Window()
    try:
        Gtk.main()
    except KeyboardInterrupt:
        pass
    return 0


def main() -> int:
    return run_gui()
