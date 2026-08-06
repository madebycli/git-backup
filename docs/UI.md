# UI design family

GitHub Backup Deck is intentionally a sibling of the GIF Picker, not a generic
desktop settings window.

## Shared window logic

The following behavior is shared directly with the GIF Picker reference:

- undecorated `Gtk.Window` top level;
- `GtkLayerShell.Layer.OVERLAY`;
- exclusive keyboard mode;
- no exclusive screen zone;
- no movable or tileable conventional window frame;
- target width `8 × (124 + 44) + 72 = 1416`;
- target height `980`;
- monitor margins of `120` horizontal and `160` vertical logical pixels;
- minimum fallback size `720 × 560`;
- rounded root surface, pill controls, monospace labels and Escape closing.

The form factor is defined once in `gui/layout.py` and covered by unit tests.

## Theme integration

The geometry and component language follow the GIF Picker. Color is obtained
from GTK3 theme symbols instead of hard-coded white:

- `@theme_bg_color` and `@theme_fg_color` for surfaces and text;
- `@theme_selected_bg_color` and `@theme_selected_fg_color` for the accent,
  selected chips, primary action and progress bar.

This lets the application follow the active GTK3 accent/theme while remaining
recognizable as part of the picker family.

## Layout stability

Dynamic labels are constrained to fixed allocations and use end ellipsis.
Buttons have fixed width and height. Account and destination cards have fixed
heights. The options area has two predetermined rows. Progress controls do not
change their labels or positions while a job runs. The live log is contained in
a fixed scroller and trims older entries beyond 2,000 lines.

Long paths, repository counts, errors and progress text therefore cannot resize
the overlay or move adjacent controls.

## Background attachment

The UI never owns the backup thread. It polls the protocol-v3 Unix socket for a
bounded event stream and current job snapshot. Destroying the overlay only
detaches the client. Reopening it resumes the same progress and log view.

The folder selector uses `Gtk.FileChooserNative`; while it is active, the parent
overlay temporarily releases exclusive keyboard mode and restores it afterward.
