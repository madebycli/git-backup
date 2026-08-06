from github_backup_deck.gui.layout import picker_window_size


def test_layout_matches_gif_picker_reference() -> None:
    assert picker_window_size(None, None) == (1416, 980)
    assert picker_window_size(1920, 1080) == (1416, 920)
    assert picker_window_size(800, 600) == (720, 560)
