from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal

from github_backup_deck.models import utc_now

EventKind = Literal["info", "progress", "success", "warning", "error"]


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    kind: EventKind
    message: str
    repository: str | None = None
    current: int | None = None
    total: int | None = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(self, "timestamp", utc_now())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EventSink = Callable[[ProgressEvent], None]


def null_sink(_event: ProgressEvent) -> None:
    return None
