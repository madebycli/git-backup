from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StorageLocation:
    path: Path
    label: str
    kind: str

    @property
    def display(self) -> str:
        return f"{self.label} — {self.path}"
