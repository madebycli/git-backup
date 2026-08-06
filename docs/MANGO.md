# Mango integration

GitHub Backup Deck sets the Wayland application ID `github-backup-deck` for its
normal GTK toplevel window. Mango's current window-rule syntax uses
`windowrule=` with `appid`, `isfloating`, `width`, `height`, `offsetx` and
`offsety` parameters.

Add this line to `~/.config/mango/config.conf`:

```ini
windowrule=isfloating:1,width:960,height:640,offsetx:0,offsety:0,appid:^github-backup-deck$
```

`isfloating:1` forces a floating window. Floating windows are centered by
default; explicit zero offsets keep the requested position at the screen
center. The width and height are pixel values.

Reload Mango using the compositor's configured reload binding. The separate
backup overview is a GtkLayerShell surface on the overlay layer, reserves no
exclusive zone and closes with Escape; it does not need this window rule.

This example was checked against the official Mango “Rules” documentation for
the current development version in August 2026.
