# UI design family

GitHub Backup Deck is intentionally implemented as a sibling of the GIF Picker,
not as a generic desktop settings window.

The shared window language includes:

- `Gtk.Window` with no server-side or client-side decoration;
- `GtkLayerShell.Layer.OVERLAY`;
- exclusive keyboard mode;
- no exclusive screen zone;
- a centered monitor-adaptive requested size derived from the picker form factor;
- rounded near-black root surface with subtle white borders;
- monochrome pill buttons and toggles;
- monospace labels, compact uppercase section headings and low-contrast hints;
- Escape and keyboard-first actions.

GIF-specific search, category chips, profile chips and thumbnail flow boxes are
removed. Their layout roles are reused for account state, automatic repository
inventory, destination state, backup content, versioned snapshot format,
progress and the live operation log.

The login dialog is itself an overlay layer-shell surface and follows the same
CSS classes. It does not block GTK while GitHub CLI is running.
