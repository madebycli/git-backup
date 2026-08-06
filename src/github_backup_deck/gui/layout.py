from __future__ import annotations

THUMB_SIZE = 124
PICKER_TARGET_WIDTH = 8 * (THUMB_SIZE + 44) + 72
PICKER_TARGET_HEIGHT = 980
PICKER_MIN_WIDTH = 720
PICKER_MIN_HEIGHT = 560
PICKER_MONITOR_X_MARGIN = 120
PICKER_MONITOR_Y_MARGIN = 160


def picker_window_size(
    monitor_width: int | None,
    monitor_height: int | None,
) -> tuple[int, int]:
    width = PICKER_TARGET_WIDTH
    height = PICKER_TARGET_HEIGHT
    if monitor_width is not None:
        width = min(
            PICKER_TARGET_WIDTH,
            max(PICKER_MIN_WIDTH, monitor_width - PICKER_MONITOR_X_MARGIN),
        )
    if monitor_height is not None:
        height = min(
            PICKER_TARGET_HEIGHT,
            max(PICKER_MIN_HEIGHT, monitor_height - PICKER_MONITOR_Y_MARGIN),
        )
    return width, height
