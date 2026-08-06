# Architecture

GitHub Backup Deck separates presentation, orchestration, GitHub access,
storage, snapshots and persistence.

- `auth/` wraps GitHub CLI status and PTY-backed browser authentication.
- `github/` calls `gh api` and normalizes repository/metadata responses.
- `backup/` plans jobs, maintains complete Git mirrors, writes metadata,
  creates versioned repository snapshots and verifies output.
- `storage/` discovers common mount points and probes candidate destinations.
- `state.py` records run and repository results in SQLite.
- `ipc/` exposes newline-delimited JSON over an XDG Unix socket.
- `gui/` implements the GIF Picker-family layer-shell window and overview.
- `terminal.py` provides a non-shell terminal fallback for interactive login.

The incremental mirror is the current synchronization source. It is updated with
`+refs/*:refs/*`, Git LFS is fetched, and `git fsck --full` runs before the
mirror is copied into a new immutable snapshot. Each snapshot has a manifest and
contains one ZIP or folder per repository.

External commands are always argument arrays with explicit timeouts. No shell
command chain is used. Configuration contains preferences and paths only;
GitHub credentials remain under management of `gh`.

## Event flow

Backup operations emit immutable `ProgressEvent` values. CLI output, the
layer-shell progress bar, the live log and IPC clients consume the same events
without coupling business logic to GTK.

## Runtime paths

- Config: `$XDG_CONFIG_HOME/github-backup-deck/config.json`
- State: `$XDG_STATE_HOME/github-backup-deck/state.sqlite3`
- Runtime socket: `$XDG_RUNTIME_DIR/github-backup-deck/control.sock`
- Cache: `$XDG_CACHE_HOME/github-backup-deck/`

All fallbacks are derived from the current user's home directory.
