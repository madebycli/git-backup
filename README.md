# GitHub Backup Deck

Current release: **0.3.2**. Runtime, Python package metadata and Nix package
version are derived from one canonical version file and verified during the Nix
install check.

GitHub Backup Deck is a Wayland layer-shell backup manager in the same visual
family as `madebycli/GIF-Player` and its GIF Picker. It discovers every
repository visible to the active GitHub CLI account, downloads every advertised
Git ref and optional Git LFS object, exports GitHub metadata, verifies the
result and only then publishes the selected output format.

Authentication is delegated to GitHub CLI. The application never asks for or
stores a personal access token.

## Install from the pinned catalog

```bash
nix profile add github:madebycli/nix-pkgs#github-backup-deck
```

Update an existing profile entry:

```bash
nix profile upgrade github-backup-deck --refresh
```

Run the overlay:

```bash
github-backup-deck
```

## GIF Picker family interface

The main window uses the GIF Picker window model rather than a movable desktop
window:

- undecorated `GtkLayerShell.Layer.OVERLAY` surface;
- exclusive keyboard focus and Escape-to-close behavior;
- the exact GIF Picker target form factor: `1416 × 980` logical pixels;
- the same monitor margins and `720 × 560` minimum fallback;
- rounded picker surface, pill controls and monospace typography;
- GTK3 theme foreground, background and selected/accent colors;
- fixed control geometry, ellipsized dynamic labels and a bounded live log;
- keyboard shortcuts: `Ctrl+L` login, `Ctrl+R` rescan and `Ctrl+B` backup.

The old descriptive subtitle below the title has been removed.

## Background jobs

The overlay is only a client. A protocol-v3 user daemon performs the actual
backup. After pressing **Start backup**, the overlay may be closed immediately.
The daemon keeps downloading, verifying and writing logs. Opening the overlay
again reconnects to the same job and restores its current progress and log.

A completed, incomplete, failed or cancelled job sends a desktop notification.
**Cancel backup** terminates active `git`/`gh` process groups, stops Python copy,
compression and verification loops, and removes temporary staging data.

No system-wide root service is installed. The daemon is launched on demand in
the current desktop session.

## Login

The preferred flow runs `gh auth login` in a background PTY, shows and copies
the one-time device code and opens the browser. A fallback button opens the
same login in Ghostty, kitty, foot, Alacritty, Konsole, GNOME Terminal or xterm.

```bash
gh auth login --hostname github.com --web --git-protocol https
```

## Verified publication model

No repository is added manually. The application requests repositories for
which the active account is owner, collaborator or organization member,
including private repositories when authorized.

Each run follows an all-or-nothing pipeline:

1. clear stale staging left by an interrupted older run;
2. download into a hidden staging directory next to the selected destination;
3. force `+refs/*:refs/*` and fetch all advertised branches, tags, notes and
   pull refs;
4. fetch every Git LFS object when enabled;
5. run `git fsck --full`, compare remote and local refs and validate metadata;
6. hash every exported file with SHA-256;
7. create exactly one selected format per repository: ZIP **or** folder;
8. verify every checksum in staging;
9. atomically publish the complete run;
10. verify every checksum again at the final path;
11. clear staging in a `finally` path.

If one repository or final verification fails, the run is not published and an
existing good `current` backup is preserved.

Default versioned ZIP layout:

```text
DESTINATION/
└── runs/
    └── YYYYMMDD-HHMMSS-RUNID/
        ├── manifest.json
        └── repositories/
            └── OWNER/
                └── REPOSITORY.zip
```

Folder mode replaces only `REPOSITORY.zip` with `REPOSITORY/`. When versioned
runs are disabled, the same verified layout is atomically published under
`DESTINATION/current/`.

Working mirrors and metadata are never published beside the selected output.
Directories created by version 0.2 (`repositories/`, `metadata/`, `snapshots/`
and `manifests/`) are legacy data and are intentionally not deleted
silently.

## Nix runtime hardening

The package creates a dedicated compiled GSettings schema directory containing
`org.gtk.Settings.FileChooser` and exports it through `GSETTINGS_SCHEMA_DIR`.
This prevents the GTK file chooser abort previously seen on NixOS. `doctor`
checks the schema explicitly, and the package install check fails when it is
missing.

## CLI

```text
github-backup-deck gui
github-backup-deck login
github-backup-deck backup
github-backup-deck cancel
github-backup-deck status
github-backup-deck overview
github-backup-deck probe PATH
github-backup-deck verify
github-backup-deck doctor
```

## Development

```bash
nix develop
python -m compileall -q src
pytest -q
ruff check .
mypy src
nix flake check --print-build-logs
nix build .#github-backup-deck --print-build-logs
```

See `docs/UI.md`, `docs/ARCHITECTURE.md`, `docs/STABILITY.md` and
`docs/SECURITY.md`.
