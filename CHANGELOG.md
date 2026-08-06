# Changelog

All notable application changes are documented here.

## 0.3.4 — 2026-08-06

### Changed

- Replaced GTK theme accent colors in the main interface with the monochrome palette used by the GIF Picker.
- Buttons, toggles, focus outlines, the status chip, spinner, scrollbar and progress fill now use neutral white alpha levels on the Picker's dark background.
- The main progress fill remains inset inside its trough and no longer inherits a green GTK accent color.
- Added regression checks that prevent GTK theme accent variables from returning to the main UI stylesheet.

### Release scope

- Application UI and tests only.
- No Nix, NixOS, flake, lock-file, catalog, module, authentication or backup-engine changes are included.

## 0.3.3 — 2026-08-06

### Fixed

- Empty GitHub repositories with an unborn `HEAD` are now treated as valid repositories instead of failing the complete backup run.
- Git LFS fetch and verification no longer try to resolve `HEAD` when a mirror contains no commits.
- Added a real bare-repository regression test for the empty-repository case.
- The progress fill now has an actual inner inset inside the trough, so it no longer paints over the rounded border at either end.

### Release scope

- Application repository only.
- No Nix, NixOS, flake, lock-file, catalog, or module changes are included.

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
