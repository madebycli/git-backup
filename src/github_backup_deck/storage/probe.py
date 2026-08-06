from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ProbeResult:
    path: str
    exists: bool
    writable: bool
    free_bytes: int
    total_bytes: int
    filesystem_device: int | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.writable and self.error is None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ok"] = self.ok
        return data


def probe_path(path: Path, *, create: bool = True) -> ProbeResult:
    target = path.expanduser().resolve()
    try:
        if create:
            target.mkdir(parents=True, exist_ok=True)
        exists = target.is_dir()
        if not exists:
            return ProbeResult(str(target), False, False, 0, 0, None, "not a directory")
        usage = shutil.disk_usage(target)
        device = target.stat().st_dev
        writable = _write_probe(target)
        return ProbeResult(
            str(target),
            True,
            writable,
            usage.free,
            usage.total,
            device,
            None if writable else "write probe failed",
        )
    except OSError as exc:
        return ProbeResult(str(target), target.exists(), False, 0, 0, None, str(exc))


def _write_probe(path: Path) -> bool:
    try:
        fd, name = tempfile.mkstemp(prefix=".github-backup-deck-probe-", dir=path)
        with os.fdopen(fd, "wb") as handle:
            handle.write(b"probe")
            handle.flush()
            os.fsync(handle.fileno())
        Path(name).unlink()
        return True
    except OSError:
        return False
