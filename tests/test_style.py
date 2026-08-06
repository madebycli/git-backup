from __future__ import annotations

from pathlib import Path


def test_main_ui_uses_gif_picker_monochrome_palette() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "src/github_backup_deck/gui/style.css").read_text(encoding="utf-8")

    assert "rgba(14, 14, 14, 0.97)" in css
    assert "rgba(255, 255, 255, 0.14)" in css
    assert "@theme_selected_bg_color" not in css
    assert "@theme_selected_fg_color" not in css
    assert "@theme_fg_color" not in css
    assert "@theme_bg_color" not in css


def test_progress_bar_is_neutral_and_inset() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "src/github_backup_deck/gui/style.css").read_text(encoding="utf-8")

    progress_block = css.split(".deck-progress progress {", maxsplit=1)[1].split("}", maxsplit=1)[0]
    trough_block = css.split(".deck-progress trough {", maxsplit=1)[1].split("}", maxsplit=1)[0]

    assert "rgba(255, 255, 255, 0.42)" in progress_block
    assert "padding: 2px" in trough_block
