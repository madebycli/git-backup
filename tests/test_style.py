from __future__ import annotations

from pathlib import Path


def _stylesheet() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "src/github_backup_deck/gui/style.css").read_text(encoding="utf-8")


def _block(css: str, selector: str) -> str:
    return css.split(f"{selector} {{", maxsplit=1)[1].split("}", maxsplit=1)[0]


def test_main_ui_uses_picker_base_with_sparse_gtk_accents() -> None:
    css = _stylesheet()

    assert "rgba(14, 14, 14, 0.97)" in css
    assert "rgba(255, 255, 255, 0.04)" in _block(css, ".chip")
    assert "@theme_selected_bg_color" in css
    assert "@theme_selected_fg_color" in css
    assert "@theme_fg_color" not in css
    assert "@theme_bg_color" not in css

    # Accent usage must stay focused instead of tinting the entire interface.
    assert 6 <= css.count("@theme_selected_bg_color") <= 12
    assert "@theme_selected_bg_color" not in _block(css, ".action-btn")
    assert "@theme_selected_bg_color" not in _block(css, ".status-chip")
    assert "@theme_selected_bg_color" not in _block(css, ".deck-card")


def test_selected_controls_use_subtle_accent_not_solid_fill() -> None:
    css = _stylesheet()
    checked = _block(css, ".chip:checked")

    assert "alpha(@theme_selected_bg_color, 0.10)" in checked
    assert "alpha(@theme_selected_bg_color, 0.62)" in checked


def test_primary_action_and_progress_use_gtk_accent() -> None:
    css = _stylesheet()
    primary = _block(css, ".primary-btn")
    progress = _block(css, ".deck-progress progress")
    trough = _block(css, ".deck-progress trough")

    assert "alpha(@theme_selected_bg_color, 0.38)" in primary
    assert "@theme_selected_fg_color" in primary
    assert "alpha(@theme_selected_bg_color, 0.78)" in progress
    assert "padding: 2px" in trough
