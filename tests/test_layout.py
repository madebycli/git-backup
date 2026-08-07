from pathlib import Path

from github_backup_deck.gui.layout import picker_window_size


def test_layout_matches_gif_picker_reference() -> None:
    assert picker_window_size(None, None) == (1416, 980)
    assert picker_window_size(1920, 1080) == (1416, 920)
    assert picker_window_size(800, 600) == (720, 560)


def test_options_panel_is_compact_split_alignment() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/github_backup_deck/gui/main_window.py").read_text(encoding="utf-8")

    assert "card.set_size_request(-1, 96)" in source
    assert "content.set_halign(Gtk.Align.START)" in source
    assert "content_row.set_halign(Gtk.Align.START)" in source
    assert "output.set_halign(Gtk.Align.END)" in source
    assert "output_row.set_halign(Gtk.Align.END)" in source
    assert 'output_title = self._label("OUTPUT", "section-label", 1.0)' in source
    assert "card.pack_start(content, False, False, 0)" in source
    assert "card.pack_end(output, False, False, 0)" in source
    assert "height=174" not in source


def test_progress_reserves_less_height_for_larger_log() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/github_backup_deck/gui/main_window.py").read_text(encoding="utf-8")

    assert "box.set_size_request(-1, 68)" in source
    assert "box.set_size_request(-1, 84)" not in source
