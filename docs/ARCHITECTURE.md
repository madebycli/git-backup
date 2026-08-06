# Architecture

GitHub Backup Deck separates presentation, job ownership, GitHub access,
staging, publication and persistence.

- `auth/` wraps GitHub CLI status and PTY-backed browser authentication.
- `github/` calls `gh api` and normalizes repository and metadata responses.
- `backup/` downloads complete Git mirrors, writes metadata, hashes exports,
  verifies output and atomically publishes a run.
- `daemon.py` owns the long-running job independently of any UI process.
- `ipc/` exposes protocol-v3 newline-delimited JSON over a versioned XDG Unix
  socket.
- `state.py` records completed summaries in SQLite.
- `gui/` implements the GIF Picker-family overlay and reconnecting job client.
- `notifications.py` sends best-effort desktop notifications with `notify-send`.
- `terminal.py` provides a non-shell terminal fallback for interactive login.

## Job lifetime

`IpcClient.ensure_server()` launches `github-backup-deck-daemon` detached from
the overlay when no compatible protocol-v3 socket exists. The daemon accepts
`status`, `start_backup` and `cancel_backup`. Only one job may run at a time.

Job status is atomically persisted under the XDG state directory. Current job
events are also appended to a bounded-per-run JSONL log, so UI clients can
reconnect after being closed. A daemon restart marks an interrupted job as
failed instead of pretending it is still active.

## Staging and publication

The selected destination is not used as a working tree. A fixed hidden staging
directory is created next to it on the same filesystem. A non-blocking `flock`
prevents UI, CLI or daemon processes from modifying one destination
concurrently.

The staging directory is removed before work begins and from a `finally` block.
An unexpected hard process kill may leave staging temporarily, but the next run
removes it before downloading anything.

For each repository:

1. `git clone --mirror` creates a temporary bare mirror;
2. the fetch refspec is forced to `+refs/*:refs/*`;
3. Git and optional LFS data are fetched with cancellable process groups;
4. remote refs are compared with local refs, with one race-safe refetch retry;
5. metadata JSON and JSONL files are parsed and validated;
6. every source file receives a SHA-256 entry;
7. exactly one ZIP or folder export is generated and checksum-verified.

The complete publish tree is verified before rename and re-verified afterward.
Versioned runs use a unique path. Non-versioned `current` publication keeps the
previous directory until post-publication verification succeeds, allowing
rollback on a final-device error.

## Cancellation

A single `threading.Event` is propagated from the daemon through planning,
`gh api`, Git operations, hashing, copying, ZIP streaming and final verification.
External commands run in their own process group; cancellation sends SIGTERM
and escalates to SIGKILL after a bounded grace period.

## Runtime paths

- Config: `$XDG_CONFIG_HOME/github-backup-deck/config.json`
- SQLite state: `$XDG_STATE_HOME/github-backup-deck/state.sqlite3`
- Job status: `$XDG_STATE_HOME/github-backup-deck/job-status.json`
- Job events: `$XDG_STATE_HOME/github-backup-deck/job-events.jsonl`
- Daemon log: `$XDG_STATE_HOME/github-backup-deck/daemon.log`
- Protocol socket: `$XDG_RUNTIME_DIR/github-backup-deck/control-v3.sock`

No root service or credential file is created.
