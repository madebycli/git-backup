from __future__ import annotations

import tomllib
from pathlib import Path

import github_backup_deck


def test_runtime_version_matches_canonical_file() -> None:
    version_file = Path(github_backup_deck.__file__).with_name("VERSION")
    expected = version_file.read_text(encoding="utf-8").strip()

    assert expected
    assert github_backup_deck.__version__ == expected


def test_packaging_uses_canonical_version_file() -> None:
    root = Path(__file__).resolve().parents[1]
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    nix_package = (root / "nix" / "package.nix").read_text(encoding="utf-8")

    assert "version" in pyproject["project"]["dynamic"]
    assert pyproject["tool"]["setuptools"]["dynamic"]["version"]["file"] == [
        "src/github_backup_deck/VERSION"
    ]
    assert "builtins.readFile ../src/github_backup_deck/VERSION" in nix_package
    assert 'github-backup-deck" --version' in nix_package
