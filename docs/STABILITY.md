# Stability audit for 0.3.0

This audit compares the implementation with the requested GIF Picker family
behavior and the failure observed in 0.1/0.2.

## Corrected findings

| Finding | Risk | Correction |
|---|---|---|
| Main height was `900`, not GIF Picker `980` | Visual drift | Exact shared form-factor constants and tests |
| Dynamic labels could request wider layouts | Buttons and cards move | Fixed allocations, ellipsis and bounded log |
| Backup ran in the UI process | Closing overlay stopped visibility/job | Detached user daemon and reconnecting client |
| No cancellation path | Long jobs could not be stopped | Cooperative event plus process-group termination |
| File chooser schema absent in Nix runtime | Immediate GLib `SIGABRT` | Compiled runtime schemas and `doctor` assertion |
| Working mirrors were written into destination | ZIP mode still showed folders | Isolated sibling staging and clean publication tree |
| ZIP/folder choice did not control all output | Mixed end layout | One chosen per-repository export format only |
| Staging could accumulate | Disk clutter | Clear before and in `finally`; next-run stale cleanup |
| `git fsck` alone did not prove ref completeness | Missing branches possible | Compare every advertised remote ref with local mirror |
| Publication was not rechecked at final path | Device write errors unnoticed | SHA-256 verification before and after atomic rename |
| Concurrent UI/CLI starts could share a mirror | Repository corruption | Destination-specific non-blocking file lock |
| Invalid JSON config could abort startup | UI unavailable | Quarantine invalid config and load safe defaults |

## Remaining environment boundary

CI can validate package construction, schemas, Python behavior and NixOS module
integration, but it cannot visually exercise every real Mango/Wayland compositor,
GTK theme and portal combination. The native chooser, theme symbols and
LayerShell calls therefore retain defensive fallbacks and are also exposed by
`doctor` for local validation.
