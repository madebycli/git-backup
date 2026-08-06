# GitHub Backup Deck

GitHub Backup Deck is a Python 3.12, GTK3 and Wayland application that backs up
all repositories visible to the currently authenticated GitHub CLI account.
It creates Git mirrors, downloads Git LFS objects, stores repository metadata
as JSON/JSONL and records run state in SQLite.

The application never asks for a personal access token. Login is performed by:

```bash
gh auth login --hostname github.com --web --git-protocol https
```

## Features

- Browser-based GitHub CLI login
- Folder chooser for home directories, USB media and external disks
- Writable/free-space probe before backup
- Mirror clone or remote update for every accessible repository
- Optional issues, pull requests and release metadata
- Git LFS object fetch
- Atomic metadata/config writes
- SQLite run history and machine-readable status
- GTK3 dashboard and GtkLayerShell status overview
- Unix-socket IPC for a reusable background process
- Reproducible Nix package, flake checks and NixOS module

## Run with Nix

```bash
nix develop
nix flake check --print-build-logs
nix build .#github-backup-deck --print-build-logs
nix run .#github-backup-deck
nix run .#github-backup-deck -- doctor
```

Install into a profile:

```bash
nix profile add github:madebycli/git-backup
```

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

The default backup directory is `~/GitHub Backup`. It can be changed in the GUI
or with `github-backup-deck backup --destination PATH`.

## Backup layout

```text
DESTINATION/
├── repositories/
│   └── OWNER/
│       └── REPOSITORY.git/
├── metadata/
│   └── OWNER/
│       └── REPOSITORY/
│           ├── repository.json
│           ├── issues.jsonl
│           ├── pulls.jsonl
│           └── releases.jsonl
└── manifests/
    └── RUN-ID.json
```

## NixOS module

```nix
{
  inputs.github-backup-deck.url = "github:madebycli/git-backup";

  outputs = { nixpkgs, github-backup-deck, ... }: {
    nixosConfigurations.nyx = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        github-backup-deck.nixosModules.default
        {
          programs.github-backup-deck.enable = true;
        }
      ];
    };
  };
}
```

The module installs a user application only. It creates no root service, no
home directory and no credentials.

## Development

```bash
python -m compileall -q src
pytest -q
ruff check .
mypy src
```

GTK imports are lazy so the CLI tests run without an active graphical session.
See `docs/ARCHITECTURE.md`, `docs/MANGO.md` and `docs/SECURITY.md` for details.
