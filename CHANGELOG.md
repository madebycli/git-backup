# Changelog

All notable application changes are documented here.

## 0.3.2 — 2026-08-06

### Fixed

- Fixed the stale CLI version output that could still report `0.3.0` after installing release `0.3.1`.
- Runtime version reporting now reads the canonical `src/github_backup_deck/VERSION` file.
- Added regression coverage so the runtime and Python package metadata cannot silently drift apart again.
- Inset the main progress bar by 12 pixels on both sides so it no longer overlaps the surrounding layout.

### Release scope

- No backup-engine behavior was changed.
- No authentication behavior was changed.
- No Nix or NixOS integration files are changed by this release-preparation commit.
