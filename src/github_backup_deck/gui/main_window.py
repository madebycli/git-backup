from __future__ import annotations

import signal
import threading
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from github_backup_deck.app import BackupApplication
from github_backup_deck.auth.github_cli import GitHubCliAuth
from github_backup_deck.config import AppConfig, ConfigStore
from github_backup_deck.gui.layout import picker_window_size
from github_backup_deck.gui.login_dialog import run_login
from github_backup_deck.gui.storage_dialog import choose_storage
from github_backup_deck.ipc.client import IpcClient
from github_backup_deck.storage.probe import probe_path


def _gtk() -> tuple[Any, Any, Any, Any, Any]:
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, GLib, Gtk, GtkLayerShell, Pango

    return Gtk, Gdk, GLib, GtkLayerShell, Pango


def run_gui() -> int:
    Gtk, Gdk, GLib, GtkLayerShell, Pango = _gtk()

    class Window(Gtk.Window):
        MAX_LOG_LINES = 2000

        def __init__(self) -> None:
            super().__init__(type=Gtk.WindowType.TOPLEVEL)
            self.store = ConfigStore()
            self.config = self.store.load()
            self.app = BackupApplication(config=self.store)
            self.auth = GitHubCliAuth()
            self.ipc = IpcClient()
            self.alive = True
            self.scanning = False
            self.authenticated = False
            self.repositories: list[Any] = []
            self.last_sequence = 0
            self.job_state = "idle"
            self._window_setup()
            self._css()
            self._ui()
            self.connect("key-press-event", self._key)
            self.connect("destroy", self._destroyed)
            self.show_all()
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self._signal_quit)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._signal_quit)
            GLib.idle_add(self._start)

        def _window_setup(self) -> None:
            self.set_title("GitHub Backup Deck")
            self.set_app_paintable(True)
            self.set_decorated(False)
            self.set_resizable(False)
            monitor_width: int | None = None
            monitor_height: int | None = None
            display = Gdk.Display.get_default()
            if display is not None:
                monitor = display.get_primary_monitor()
                if monitor is None and display.get_n_monitors() > 0:
                    monitor = display.get_monitor(0)
                if monitor is not None:
                    geometry = monitor.get_geometry()
                    monitor_width = geometry.width
                    monitor_height = geometry.height
            width, height = picker_window_size(monitor_width, monitor_height)
            self.set_size_request(width, height)
            self.set_default_size(width, height)
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

        def _label(
            self,
            text: str,
            css: str,
            xalign: float = 0.0,
            *,
            width_chars: int | None = None,
        ) -> Any:
            widget = Gtk.Label(label=text)
            widget.set_xalign(xalign)
            widget.set_single_line_mode(True)
            widget.set_ellipsize(Pango.EllipsizeMode.END)
            if width_chars is not None:
                widget.set_width_chars(min(width_chars, 24))
                widget.set_max_width_chars(width_chars)
                widget.set_hexpand(True)
            widget.set_tooltip_text(text)
            widget.get_style_context().add_class(css)
            return widget

        def _button(
            self,
            text: str,
            css: str,
            callback: Callable[..., object],
            *,
            width: int = 142,
        ) -> Any:
            widget = Gtk.Button(label=text)
            widget.set_size_request(width, 36)
            widget.get_style_context().add_class(css)
            widget.connect("clicked", callback)
            return widget

        @staticmethod
        def _margins(widget: Any, value: int) -> None:
            for side in ("top", "bottom", "start", "end"):
                getattr(widget, f"set_margin_{side}")(value)

        def _card(self, title: str, *, height: int = 150) -> Any:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            box.set_size_request(-1, height)
            box.get_style_context().add_class("deck-card")
            box.pack_start(self._label(title, "section-label", width_chars=56), False, False, 0)
            return box

        def _toggle(self, text: str, active: bool, *, width: int = 116) -> Any:
            widget = Gtk.CheckButton(label=text)
            widget.set_mode(False)
            widget.set_active(active)
            widget.set_size_request(width, 34)
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
                    width_chars=92,
                ),
                False,
                False,
                0,
            )
            root.pack_start(body, True, True, 0)
            self.add(root)

        def _header(self) -> Any:
            header = Gtk.Grid()
            header.set_column_spacing(10)
            header.set_hexpand(True)
            header.set_size_request(-1, 32)
            header.set_margin_top(6)
            header.set_margin_bottom(6)
            header.set_margin_start(12)
            header.set_margin_end(12)

            close = self._button("✕", "x-btn", lambda *_: self._close(), width=32)
            close.set_size_request(32, 32)
            header.attach(close, 0, 0, 1, 1)

            title = self._label("GitHub Backup Deck", "picker-title")
            title.set_halign(Gtk.Align.START)
            header.attach(title, 1, 0, 1, 1)

            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            header.attach(spacer, 2, 0, 1, 1)

            self.head = self._label("READY", "status-chip", 0.5)
            self.head.set_size_request(96, 30)
            self.head.set_halign(Gtk.Align.END)
            header.attach(self.head, 3, 0, 1, 1)
            return header

        def _account_card(self) -> Any:
            card = self._card("GITHUB ACCOUNT")
            self.account = self._label("Not signed in", "card-title", width_chars=48)
            self.repo_count = self._label("Repository scan waiting", "card-detail", width_chars=64)
            card.pack_start(self.account, False, False, 0)
            card.pack_start(self.repo_count, False, False, 0)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.login = self._button("Sign in", "action-btn", self._login)
            self.scan = self._button(
                "Scan repositories",
                "chip",
                lambda *_: self._scan(),
                width=160,
            )
            row.pack_start(self.login, False, False, 0)
            row.pack_start(self.scan, False, False, 0)
            card.pack_end(row, False, False, 0)
            return card

        def _destination_card(self) -> Any:
            card = self._card("BACKUP DESTINATION")
            self.destination = self._label(
                str(self.config.backup_path),
                "card-title",
                width_chars=56,
            )
            self.storage = self._label("Storage not probed", "card-detail", width_chars=64)
            card.pack_start(self.destination, False, False, 0)
            card.pack_start(self.storage, False, False, 0)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.pack_start(
                self._button("Choose folder", "action-btn", self._choose),
                False,
                False,
                0,
            )
            row.pack_start(
                self._button("Probe", "chip", lambda *_: self._probe(), width=108),
                False,
                False,
                0,
            )
            card.pack_end(row, False, False, 0)
            return card

        def _options(self) -> Any:
            card = self._card(
                "BACKUP CONTENT · ALL ACCESSIBLE REPOSITORIES · EVERY GIT REF",
                height=174,
            )
            first = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.issues = self._toggle("Issues", self.config.include_issues)
            self.pulls = self._toggle("Pull requests", self.config.include_pull_requests)
            self.releases = self._toggle("Releases", self.config.include_releases)
            self.archived = self._toggle("Archived repos", self.config.include_archived)
            self.lfs = self._toggle("Git LFS", self.config.fetch_lfs)
            for widget in (self.issues, self.pulls, self.releases, self.archived, self.lfs):
                first.pack_start(widget, False, False, 0)
            card.pack_start(first, False, False, 0)
            second = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            second.pack_start(
                self._label("Output", "card-detail", width_chars=12),
                False,
                False,
                0,
            )
            self.zip = Gtk.RadioButton.new_with_label_from_widget(None, "ZIP per repository")
            self.folder = Gtk.RadioButton.new_with_label_from_widget(
                self.zip, "Folder per repository"
            )
            for widget in (self.zip, self.folder):
                widget.set_mode(False)
                widget.set_size_request(170, 34)
                widget.get_style_context().add_class("chip")
                second.pack_start(widget, False, False, 0)
            self.zip.set_active(self.config.backup_format == "zip")
            self.folder.set_active(self.config.backup_format == "folder")
            self.versioned = self._toggle(
                "Keep versioned runs",
                self.config.versioned_snapshots,
                width=190,
            )
            second.pack_start(self.versioned, False, False, 0)
            card.pack_start(second, False, False, 0)
            return card

        def _progress(self) -> Any:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_size_request(-1, 84)
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.status = self._label("Ready", "card-detail", width_chars=40)
            self.backup = self._button("Start backup", "primary-btn", self._backup, width=164)
            self.cancel = self._button(
                "Cancel backup",
                "danger-btn",
                self._cancel_backup,
                width=164,
            )
            self.cancel.set_sensitive(False)
            row.pack_start(self.status, True, True, 0)
            row.pack_end(self.cancel, False, False, 0)
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
            row.pack_start(
                self._label("LIVE LOG", "section-label", width_chars=20),
                False,
                False,
                0,
            )
            row.pack_end(
                self._button(
                    "Clear",
                    "chip",
                    lambda *_: self.log_buffer.set_text(""),
                    width=92,
                ),
                False,
                False,
                0,
            )
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.get_style_context().add_class("log-scroll")
            self.log = Gtk.TextView()
            self.log.set_editable(False)
            self.log.set_cursor_visible(False)
            self.log.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            self.log.set_monospace(True)
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
            self._line("info", "Overlay opened; reconnecting to the background backup service")
            threading.Thread(target=self._poll_loop, name="backup-status-poll", daemon=True).start()
            self._scan()
            return False

        def _poll_loop(self) -> None:
            try:
                self.ipc.ensure_server()
            except Exception as exc:  # noqa: BLE001 - UI boundary
                GLib.idle_add(self._daemon_error, str(exc))
                return
            while self.alive:
                try:
                    response = self.ipc.request(
                        {"command": "status", "after_sequence": self.last_sequence},
                        timeout=2.0,
                    )
                    GLib.idle_add(self._apply_job_status, response)
                except Exception as exc:  # noqa: BLE001 - reconnect loop
                    GLib.idle_add(self._daemon_error, str(exc))
                time.sleep(0.5)

        def _daemon_error(self, error: str) -> bool:
            if not self.alive:
                return False
            self.head.set_text("SERVICE ERROR")
            self.status.set_text("Background service unavailable")
            self.status.set_tooltip_text(error)
            return False

        def _apply_job_status(self, response: dict[str, Any]) -> bool:
            if not self.alive or not response.get("ok"):
                return False
            for event in response.get("events", []):
                if isinstance(event, dict):
                    sequence = int(event.get("sequence", 0))
                    self.last_sequence = max(self.last_sequence, sequence)
                    self._line(
                        str(event.get("kind", "info")),
                        str(event.get("message", "")),
                        repository=(
                            str(event.get("repository"))
                            if event.get("repository")
                            else None
                        ),
                        timestamp=str(event.get("timestamp", "")),
                    )
            job = response.get("job")
            if not isinstance(job, dict):
                return False
            state = str(job.get("state", "idle"))
            self.job_state = state
            current = int(job.get("current") or 0)
            total = int(job.get("total") or 0)
            message = str(job.get("message") or "Ready")
            self.status.set_text(message)
            self.status.set_tooltip_text(message)
            active = state in {"running", "cancelling"}
            self.backup.set_sensitive(not active and self.authenticated)
            self.cancel.set_sensitive(active and state != "cancelling")
            if total > 0:
                self.bar.set_fraction(min(1.0, current / total))
                self.bar.set_text(f"{current}/{total} repositories")
            elif active:
                self.bar.pulse()
                self.bar.set_text("Preparing…")
            if state == "running":
                self.head.set_text("BACKING UP")
            elif state == "cancelling":
                self.head.set_text("CANCELLING")
            elif state == "completed":
                self.head.set_text("COMPLETE")
                self.bar.set_fraction(1.0)
                self.bar.set_text("Verified and published")
            elif state == "failed":
                self.head.set_text("ERROR")
                self.bar.set_text("Not published")
            elif state == "cancelled":
                self.head.set_text("CANCELLED")
                self.bar.set_fraction(0.0)
                self.bar.set_text("Temporary files removed")
            return False

        def _login(self, _button: Any) -> None:
            if self.job_state in {"running", "cancelling"}:
                self._line("warning", "Login cannot be changed while a backup is running")
                return
            self._line("info", "Starting GitHub browser login")
            if run_login(self):
                self.authenticated = True
                self._line("success", "GitHub login completed")
                self._scan()
            else:
                self._line("warning", "GitHub login cancelled or incomplete")

        def _choose(self, _button: Any) -> None:
            if self.job_state in {"running", "cancelling"}:
                self._line("warning", "Destination cannot change while a backup is running")
                return
            selected = choose_storage(self, self.config.backup_path)
            if selected is None:
                return
            self.config = replace(self.config, default_backup_directory=str(selected))
            self.store.save(self.config)
            self.destination.set_text(str(selected))
            self.destination.set_tooltip_text(str(selected))
            self._line("info", f"Destination changed to {selected}")
            self._probe()

        def _probe(self) -> None:
            result = probe_path(self.config.backup_path)
            text = (
                f"Writable · {result.free_bytes / (1024**3):.1f} GiB free"
                if result.ok
                else result.error or "Storage probe failed"
            )
            self.storage.set_text(text)
            self.storage.set_tooltip_text(text)

        def _scan(self) -> None:
            if self.scanning:
                return
            self.scanning = True
            self.scan.set_sensitive(False)
            self.repo_count.set_text("Checking GitHub session…")
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
                except Exception as exc:  # noqa: BLE001 - worker/UI boundary
                    GLib.idle_add(self._scan_done, None, [], str(exc))

            threading.Thread(target=worker, name="github-scan", daemon=True).start()

        def _scan_done(self, session: Any, repositories: list[Any], error: str | None) -> bool:
            if not self.alive:
                return False
            self.scanning = False
            self.scan.set_sensitive(True)
            if error:
                self.repo_count.set_text("Repository scan failed")
                self.repo_count.set_tooltip_text(error)
                self._line("error", error)
                return False
            self.authenticated = bool(session and session.authenticated)
            if not self.authenticated:
                self.account.set_text("Not signed in")
                self.login.set_label("Sign in")
                self.repo_count.set_text("Sign in to scan repositories")
                self.backup.set_sensitive(False)
                return False
            self.account.set_text(session.login or "Signed in")
            self.login.set_label("Switch account")
            self.repositories = repositories
            private = sum(bool(repo.private) for repo in repositories)
            archived = sum(bool(repo.archived) for repo in repositories)
            public = len(repositories) - private
            text = (
                f"{len(repositories)} repos · {private} private · "
                f"{public} public · {archived} archived"
            )
            self.repo_count.set_text(text)
            self.repo_count.set_tooltip_text(text)
            if self.job_state not in {"running", "cancelling"}:
                self.backup.set_sensitive(True)
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
            if self.job_state in {"running", "cancelling"}:
                return
            if not self.authenticated:
                self._login(self.login)
                return
            config = self._save()
            probe = probe_path(config.backup_path)
            if not probe.ok:
                self._line("error", probe.error or "Destination is not writable")
                return
            self.backup.set_sensitive(False)
            self.status.set_text("Starting background backup service…")
            self._ipc_async(
                {"command": "start_backup", "destination": str(config.backup_path)},
                self._start_response,
            )

        def _start_response(self, response: dict[str, Any]) -> None:
            if response.get("ok"):
                self.last_sequence = 0
                self._line(
                    "success",
                    "Backup continues in the background; this overlay may be closed",
                )
            else:
                self._line("error", str(response.get("error", "Could not start backup")))
                self.backup.set_sensitive(self.authenticated)

        def _cancel_backup(self, _button: Any) -> None:
            if self.job_state not in {"running", "cancelling"}:
                return
            self.cancel.set_sensitive(False)
            self._ipc_async({"command": "cancel_backup"}, self._cancel_response)

        def _cancel_response(self, response: dict[str, Any]) -> None:
            if response.get("ok"):
                self._line(
                    "warning",
                    "Cancellation requested; active command will be terminated safely",
                )
            else:
                self._line("error", str(response.get("error", "Could not cancel backup")))

        def _ipc_async(
            self,
            payload: dict[str, Any],
            callback: Callable[[dict[str, Any]], None],
        ) -> None:
            def worker() -> None:
                try:
                    self.ipc.ensure_server()
                    response = self.ipc.request(payload, timeout=5.0)
                except Exception as exc:  # noqa: BLE001 - IPC/UI boundary
                    response = {"ok": False, "error": str(exc)}
                GLib.idle_add(self._finish_ipc, callback, response)

            threading.Thread(target=worker, name="github-backup-ipc", daemon=True).start()

        def _finish_ipc(
            self,
            callback: Callable[[dict[str, Any]], None],
            response: dict[str, Any],
        ) -> bool:
            if self.alive:
                callback(response)
            return False

        def _line(
            self,
            kind: str,
            message: str,
            *,
            repository: str | None = None,
            timestamp: str = "",
        ) -> None:
            marker = {"success": "✓", "warning": "!", "error": "×", "progress": "→"}.get(kind, "·")
            if repository:
                message = f"{repository}: {message}"
            clock = datetime.now().strftime("%H:%M:%S")
            if timestamp:
                try:
                    clock = datetime.fromisoformat(timestamp).astimezone().strftime("%H:%M:%S")
                except ValueError:
                    pass
            end = self.log_buffer.get_end_iter()
            self.log_buffer.insert(end, f"{clock}  {marker}  {message}\n")
            line_count = self.log_buffer.get_line_count()
            if line_count > self.MAX_LOG_LINES:
                start = self.log_buffer.get_start_iter()
                trim = self.log_buffer.get_iter_at_line(line_count - self.MAX_LOG_LINES)
                self.log_buffer.delete(start, trim)
            mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
            self.log.scroll_mark_onscreen(mark)
            self.log_buffer.delete_mark(mark)

        def _close(self) -> None:
            self.destroy()

        def _destroyed(self, *_args: object) -> None:
            self.alive = False
            Gtk.main_quit()

        def _signal_quit(self) -> bool:
            self._close()
            return False

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
