from __future__ import annotations

import errno
import json
import os
import pty
import re
import selectors
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from github_backup_deck.process import CommandError, run_command

DEVICE_LOGIN_URL = "https://github.com/login/device"
_DEVICE_CODE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}\b")
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(frozen=True, slots=True)
class AuthStatus:
    installed: bool
    authenticated: bool
    login: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LoginEvent:
    message: str
    code: str | None = None
    url: str | None = None


LoginSink = Callable[[LoginEvent], None]


def _clean_output(value: str) -> str:
    return _ANSI_ESCAPE.sub("", value).strip()


def _extract_device_code(value: str) -> str | None:
    match = _DEVICE_CODE.search(_clean_output(value))
    return match.group(0) if match is not None else None


class GitHubCliAuth:
    def status(self) -> AuthStatus:
        if shutil.which("gh") is None:
            return AuthStatus(False, False, error="GitHub CLI (gh) is not installed")
        result = run_command(
            ["gh", "auth", "status", "--hostname", "github.com"],
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return AuthStatus(True, False, error=result.stderr.strip() or "not authenticated")
        login_result = run_command(
            ["gh", "api", "user", "--jq", ".login"], timeout=30, check=False
        )
        login = login_result.stdout.strip() if login_result.returncode == 0 else None
        return AuthStatus(True, True, login=login or None)

    def login(
        self,
        *,
        sink: LoginSink | None = None,
        browser_command: str | None = None,
        cancel_event: threading.Event | None = None,
    ) -> AuthStatus:
        if shutil.which("gh") is None:
            return AuthStatus(False, False, error="GitHub CLI (gh) is not installed")
        if sink is None:
            return self._interactive_login()
        return self._streaming_login(
            sink=sink,
            browser_command=browser_command,
            cancel_event=cancel_event,
        )

    def _interactive_login(self) -> AuthStatus:
        try:
            completed = subprocess.run(
                self._login_args(clipboard=True),
                env=os.environ.copy(),
                timeout=900,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return AuthStatus(True, False, error="GitHub login timed out after 900 seconds")
        except KeyboardInterrupt:
            return AuthStatus(True, False, error="GitHub login cancelled")
        if completed.returncode != 0:
            return AuthStatus(True, False, error=f"gh exited with {completed.returncode}")
        return self._finish_login()

    def _streaming_login(
        self,
        *,
        sink: LoginSink,
        browser_command: str | None,
        cancel_event: threading.Event | None,
    ) -> AuthStatus:
        environment = os.environ.copy()
        if browser_command is not None:
            environment["GH_BROWSER"] = browser_command

        master_fd, slave_fd = pty.openpty()
        try:
            try:
                process = subprocess.Popen(
                    self._login_args(clipboard=False),
                    env=environment,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    start_new_session=True,
                )
            except Exception:
                os.close(master_fd)
                raise
        finally:
            os.close(slave_fd)

        # gh currently has up to two load-bearing prompts in this flow: one to
        # accept Git credential setup and one to start browser login/polling.
        # A PTY plus two default answers preserves gh's supported browser flow
        # without blocking GTK or requiring a terminal window.
        os.write(master_fd, b"\n\n")

        output: list[str] = []
        pending = ""
        deadline = time.monotonic() + 900
        selector = selectors.DefaultSelector()
        selector.register(master_fd, selectors.EVENT_READ)
        try:
            while process.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    self._terminate(process)
                    return AuthStatus(True, False, error="GitHub login cancelled")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate(process)
                    return AuthStatus(True, False, error="GitHub login timed out after 900 seconds")
                if selector.select(timeout=min(0.25, remaining)):
                    pending = self._read_login_output(master_fd, output, pending, sink)

            while True:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                pending = self._consume_login_chunk(chunk, output, pending, sink)
        finally:
            selector.close()
            os.close(master_fd)

        if pending.strip():
            self._emit_login_line(sink, pending)
        returncode = process.wait()
        if returncode != 0:
            detail = _clean_output("".join(output)) or f"gh exited with {returncode}"
            return AuthStatus(True, False, error=detail)
        return self._finish_login()

    @classmethod
    def _read_login_output(
        cls,
        master_fd: int,
        output: list[str],
        pending: str,
        sink: LoginSink,
    ) -> str:
        try:
            chunk = os.read(master_fd, 4096)
        except OSError as exc:
            if exc.errno == errno.EIO:
                return pending
            raise
        return cls._consume_login_chunk(chunk, output, pending, sink)

    @classmethod
    def _consume_login_chunk(
        cls,
        chunk: bytes,
        output: list[str],
        pending: str,
        sink: LoginSink,
    ) -> str:
        text = chunk.decode("utf-8", errors="replace")
        output.append(text)
        pending += text.replace("\r", "\n")
        lines = pending.split("\n")
        pending = lines.pop()
        for line in lines:
            cls._emit_login_line(sink, line)
        return pending

    @staticmethod
    def _emit_login_line(sink: LoginSink, line: str) -> None:
        message = _clean_output(line)
        if not message:
            return
        code = _extract_device_code(message)
        sink(LoginEvent(message=message, code=code, url=DEVICE_LOGIN_URL if code else None))

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    @staticmethod
    def _login_args(*, clipboard: bool) -> list[str]:
        args = [
            "gh",
            "auth",
            "login",
            "--hostname",
            "github.com",
            "--web",
            "--git-protocol",
            "https",
        ]
        if clipboard:
            args.append("--clipboard")
        return args

    def _finish_login(self) -> AuthStatus:
        setup = run_command(
            ["gh", "auth", "setup-git", "--hostname", "github.com"],
            timeout=60,
            check=False,
        )
        if setup.returncode != 0:
            detail = setup.stderr.strip() or setup.stdout.strip() or "git setup failed"
            return AuthStatus(True, False, error=detail)
        return self.status()

    def diagnostics(self) -> dict[str, object]:
        status = self.status()
        return {
            "gh_installed": status.installed,
            "authenticated": status.authenticated,
            "login": status.login,
            "error": status.error,
        }

    def token_scopes(self) -> list[str]:
        try:
            result = run_command(
                ["gh", "auth", "status", "--hostname", "github.com", "--json", "tokenScopes"],
                timeout=30,
            )
            payload = json.loads(result.stdout)
            scopes = payload.get("tokenScopes", []) if isinstance(payload, dict) else []
            return [str(item) for item in scopes]
        except (CommandError, json.JSONDecodeError, RuntimeError):
            return []
