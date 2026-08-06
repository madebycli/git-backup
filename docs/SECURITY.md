# Security model

GitHub Backup Deck does not accept a token flag and never serializes a token.
Authentication uses the GitHub CLI web flow. Git and API subprocesses inherit
only the user's normal environment.

The Nix package and NixOS/Home Manager modules contain no user credentials,
backup destination or generated account data. The Nix build performs no
network access.

Metadata and configuration files are written atomically. The IPC directory is
created with mode `0700` and the Unix socket with mode `0600`. External
processes have explicit timeouts and are terminated before a timeout error is
returned.
