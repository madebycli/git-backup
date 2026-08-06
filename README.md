# GitHub Backup Deck

GitHub Backup Deck is a Wayland layer-shell backup manager in the same visual
family as `madebycli/GIF-Player` and its GIF Picker. It discovers every
repository accessible to the active GitHub CLI account, mirrors every Git ref,
exports GitHub metadata and creates versioned per-repository snapshots.

Authentication is delegated to GitHub CLI. The application never asks for or
stores a personal access token.

## Install from the pinned catalog

```bash
nix profile add github:madebycli/nix-pkgs#github-backup-deck
```

Update the installed profile entry after a new catalog pin is published:

```bash
nix profile upgrade github-backup-deck --refresh
```

Run the main layer-shell interface:

```bash
github-backup-deck
```

## GIF Picker family interface

The main window deliberately reuses the GIF Picker window model:

- undecorated `GtkLayerShell` overlay surface
- exclusive keyboard focus and Escape-to-close behavior
- monitor-adaptive picker form factor
- dark rounded picker surface, monochrome pill controls and monospace typography
- keyboard shortcuts: `Ctrl+L` login, `Ctrl+R` rescan, `Ctrl+B` backup
- full-width progress bar and detailed live log

The window automatically shows the active GitHub account, the number of
accessible repositories, private/public/archive counts, destination health and
available storage.

## Login

The preferred login flow stays inside the UI. It runs `gh auth login` in a
background PTY, displays and copies the one-time device code, and opens the
system browser. A fallback button opens the same login in the first available
terminal among Ghostty, kitty, foot, Alacritty, Konsole, GNOME Terminal and
xterm.

The underlying command remains:

```bash
gh auth login --hostname github.com --web --git-protocol https
```

## Backup model

No repository is added manually. The application requests all repositories for
which the active account is owner, collaborator or organization member,
including private repositories when authorized.

For each repository it:

1. maintains an incremental bare mirror under `repositories/`;
2. forces the mirror refspec to `+refs/*:refs/*`, preserving branches, tags,
   notes and advertised pull refs;
3. fetches every Git LFS object when enabled;
4. validates the mirror with `git fsck --full`;
5. exports repository, issue, pull-request and release metadata;
6. creates an immutable versioned snapshot.

ZIP is the default snapshot format. Every repository gets its own ZIP containing
its complete bare mirror and metadata. Folder snapshots are available from the
UI.

```text
DESTINATION/
├── repositories/                 # incremental working mirrors
│   └── OWNER/REPOSITORY.git/
├── metadata/                     # latest exported metadata
│   └── OWNER/REPOSITORY/
├── snapshots/
│   └── YYYYMMDD-HHMMSS-RUNID/
│       ├── manifest.json
│       └── repositories/
│           └── OWNER/
│               └── REPOSITORY.zip
└── manifests/
    └── RUNID.json
```

Existing mirrors are updated and a new snapshot is created on every run, so old
backup versions remain unchanged.

## CLI

```text
github-backup-deck gui
github-backup-deck login
github-backup-deck backup
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

See `docs/UI.md`, `docs/ARCHITECTURE.md` and `docs/SECURITY.md`.
