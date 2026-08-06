from __future__ import annotations

from github_backup_deck.models import Repository


def test_repository_from_api() -> None:
    repository = Repository.from_api(
        {
            "name": "demo",
            "full_name": "owner/demo",
            "clone_url": "https://github.com/owner/demo.git",
            "private": True,
            "archived": False,
        }
    )
    assert repository.full_name == "owner/demo"
    assert repository.private is True
