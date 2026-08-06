# Architecture

GitHub Backup Deck separates presentation, orchestration, GitHub access,
storage and persistence.

- `auth/` wraps GitHub CLI authentication.
- `github/` calls `gh api` and normalizes repository/metadata responses.
- `backup/` plans jobs, maintains Git mirrors, writes metadata and verifies output.
- `storage/` discovers common mount points and probes candidate destinations.
- `state.py` owns SQLite migrations and run/repository records.
- `ipc/` exposes newline-delimited JSON requests over an XDG Unix socket.
- `daemon.py` executes reusable background backup requests.
- `gui/` contains the normal GTK window and a separate layer-shell overview.

External commands are always invoked as argument arrays with timeouts. No
shell command chain is used. Configuration contains preferences and paths only;
GitHub credentials stay under management of `gh`.

## Event flow

Backup operations emit immutable `ProgressEvent` values. CLI output, GTK widgets
and IPC clients consume the same events without coupling business logic to GTK.

## Runtime paths

- Config: `$XDG_CONFIG_HOME/github-backup-deck/config.json`
- State: `$XDG_STATE_HOME/github-backup-deck/state.sqlite3`
- Runtime socket: `$XDG_RUNTIME_DIR/github-backup-deck/control.sock`
- Cache: `$XDG_CACHE_HOME/github-backup-deck/`

All fallbacks are derived from the current user's home directory.
