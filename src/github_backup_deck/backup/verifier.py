from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from github_backup_deck.process import run_command


@dataclass(frozen=True, slots=True)
class VerificationResult:
    destination: str
    mirrors_checked: int
    mirrors_failed: int
    missing_metadata: int
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.mirrors_failed == 0 and self.missing_metadata == 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["ok"] = self.ok
        return payload


def verify_destination(destination: Path) -> VerificationResult:
    destination = destination.expanduser().resolve()
    repositories_root = destination / "repositories"
    mirrors = sorted(repositories_root.glob("*/*.git")) if repositories_root.exists() else []
    errors: list[str] = []
    failed = 0
    missing_metadata = 0
    for mirror in mirrors:
        result = run_command(
            ["git", "-C", str(mirror), "fsck", "--full"],
            timeout=1800,
            check=False,
        )
        if result.returncode != 0:
            failed += 1
            errors.append(f"{mirror}: {result.stderr.strip() or 'git fsck failed'}")
        relative = mirror.relative_to(repositories_root)
        full_name = str(relative)[:-4]
        metadata = destination / "metadata" / full_name / "repository.json"
        if not metadata.is_file():
            missing_metadata += 1
            errors.append(f"Missing metadata: {metadata}")
    return VerificationResult(
        str(destination), len(mirrors), failed, missing_metadata, tuple(errors)
    )
