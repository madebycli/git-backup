from __future__ import annotations

import os
import shutil
import threading
import time
from typing import Any

from github_backup_deck.auth.github_cli import DEVICE_LOGIN_URL, GitHubCliAuth, LoginEvent
from github_backup_deck.terminal import launch_login_terminal


def run_login(parent: Any) -> bool:
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell

    dialog = Gtk.Dialog(title="Sign in to GitHub", transient_for=parent, modal=True)
    dialog.set_decorated(False)
    dialog.get_style_context().add_class("picker-root")
    dialog.set_app_paintable(True)
    dialog.set_size_request(560, 300)
    rgba = dialog.get_screen().get_rgba_visual()
    if rgba is not None:
        dialog.set_visual(rgba)
    GtkLayerShell.init_for_window(dialog)
    GtkLayerShell.set_layer(dialog, GtkLayerShell.Layer.OVERLAY)
    GtkLayerShell.set_keyboard_mode(dialog, GtkLayerShell.KeyboardMode.EXCLUSIVE)
    GtkLayerShell.set_namespace(dialog, "github-backup-login")
    GtkLayerShell.set_exclusive_zone(dialog, 0)
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    cancel_button = dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
    if cancel_button is not None:
        cancel_button.get_style_context().add_class("chip")

    content = dialog.get_content_area()
    content.get_style_context().add_class("picker-root")
    content.set_border_width(18)
    content.set_spacing(12)

    heading = Gtk.Label(label="GitHub CLI browser login")
    heading.set_xalign(0)
    heading.get_style_context().add_class("picker-title")
    content.pack_start(heading, False, False, 0)

    explanation = Gtk.Label(
        label=(
            "A browser window will open. Paste the one-time code shown below "
            "and approve GitHub CLI access. No token is entered into this app."
        )
    )
    explanation.set_xalign(0)
    explanation.set_line_wrap(True)
    explanation.get_style_context().add_class("card-detail")
    content.pack_start(explanation, False, False, 0)

    spinner = Gtk.Spinner()
    spinner.start()
    content.pack_start(spinner, False, False, 0)

    status_label = Gtk.Label(label="Starting GitHub CLI…")
    status_label.set_xalign(0)
    status_label.set_line_wrap(True)
    status_label.get_style_context().add_class("card-detail")
    content.pack_start(status_label, False, False, 0)

    code_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    code_label = Gtk.Label(label="")
    code_label.set_selectable(True)
    code_label.get_style_context().add_class("picker-title")
    code_box.pack_start(code_label, True, True, 0)
    copy_button = Gtk.Button(label="Copy code")
    copy_button.get_style_context().add_class("action-btn")
    code_box.pack_start(copy_button, False, False, 0)
    open_button = Gtk.Button(label="Open browser again")
    open_button.get_style_context().add_class("chip")
    code_box.pack_start(open_button, False, False, 0)
    code_box.set_no_show_all(True)
    content.pack_start(code_box, False, False, 0)

    fallback_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    fallback_label = Gtk.Label(label="Browser flow not working?")
    fallback_label.set_xalign(0)
    fallback_label.get_style_context().add_class("picker-hint")
    fallback_box.pack_start(fallback_label, True, True, 0)
    terminal_button = Gtk.Button(label="Open terminal login")
    terminal_button.get_style_context().add_class("chip")
    fallback_box.pack_end(terminal_button, False, False, 0)
    content.pack_start(fallback_box, False, False, 0)

    state: dict[str, Any] = {
        "active": True,
        "browser_opened": False,
        "code": None,
        "error": None,
        "done": False,
        "terminal_mode": False,
    }
    cancel_event = threading.Event()
    noop_browser = os.environ.get("GITHUB_BACKUP_DECK_NOOP_BROWSER") or shutil.which("true")
    auth = GitHubCliAuth()

    def open_browser() -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(DEVICE_LOGIN_URL, None)
            state["browser_opened"] = True
        except GLib.Error as exc:
            status_label.set_text(
                f"Could not open the browser automatically: {exc}. "
                f"Open {DEVICE_LOGIN_URL} manually."
            )

    def copy_code() -> None:
        code = state["code"]
        if not isinstance(code, str):
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(code, -1)
        clipboard.store()
        status_label.set_text("Code copied. Complete the sign-in in your browser.")

    def show_event(event: LoginEvent) -> bool:
        if not state["active"] or state["terminal_mode"]:
            return False
        status_label.set_text(event.message)
        if event.code is not None:
            state["code"] = event.code
            code_label.set_text(event.code)
            code_box.set_no_show_all(False)
            code_box.show_all()
            copy_code()
            if noop_browser is not None and not state["browser_opened"]:
                open_browser()
        return False

    def finish(authenticated: bool, error: str | None) -> bool:
        if not state["active"]:
            return False
        if state["terminal_mode"] and not authenticated:
            return False
        state["error"] = error
        state["done"] = True
        spinner.stop()
        dialog.response(Gtk.ResponseType.OK if authenticated else Gtk.ResponseType.REJECT)
        return False

    def browser_worker() -> None:
        try:
            status = auth.login(
                sink=lambda event: GLib.idle_add(show_event, event),
                browser_command=noop_browser,
                cancel_event=cancel_event,
            )
            GLib.idle_add(finish, status.authenticated, status.error)
        except Exception as exc:  # noqa: BLE001 - worker/UI boundary
            GLib.idle_add(finish, False, str(exc))

    def terminal_poll_worker() -> None:
        while state["active"] and state["terminal_mode"]:
            status = auth.status()
            if status.authenticated:
                GLib.idle_add(finish, True, None)
                return
            time.sleep(1.0)

    def open_terminal_login() -> None:
        if state["terminal_mode"]:
            return
        try:
            terminal_name = launch_login_terminal()
        except RuntimeError as exc:
            status_label.set_text(str(exc))
            return
        state["terminal_mode"] = True
        cancel_event.set()
        terminal_button.set_sensitive(False)
        spinner.start()
        status_label.set_text(
            f"Login opened in {terminal_name}. This dialog will close after authentication."
        )
        threading.Thread(
            target=terminal_poll_worker,
            name="github-terminal-login-poll",
            daemon=True,
        ).start()

    copy_button.connect("clicked", lambda _button: copy_code())
    open_button.connect("clicked", lambda _button: open_browser())
    terminal_button.connect("clicked", lambda _button: open_terminal_login())
    dialog.show_all()
    code_box.hide()
    threading.Thread(target=browser_worker, name="github-login", daemon=True).start()

    response = dialog.run()
    state["active"] = False
    if response != Gtk.ResponseType.OK:
        cancel_event.set()
    authenticated = bool(response == Gtk.ResponseType.OK)
    error_message = state["error"]
    dialog.destroy()

    if not authenticated and response != Gtk.ResponseType.CANCEL and error_message:
        error = Gtk.MessageDialog(
            transient_for=parent,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="GitHub login failed",
        )
        error.format_secondary_text(str(error_message))
        error.run()
        error.destroy()
    return authenticated
