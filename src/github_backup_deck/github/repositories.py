from __future__ import annotations

from github_backup_deck.github.client import GitHubClient
from github_backup_deck.models import Repository


class RepositoryService:
    def __init__(self, client: GitHubClient | None = None) -> None:
        self.client = client or GitHubClient()

    def list_accessible(self, *, include_archived: bool = True) -> list[Repository]:
        items = self.client.paginated_items(
            "/user/repos?per_page=100&sort=full_name&direction=asc"
            "&affiliation=owner,collaborator,organization_member",
            timeout=600,
        )
        repositories = [Repository.from_api(item) for item in items]
        if not include_archived:
            repositories = [repo for repo in repositories if not repo.archived]
        unique = {repo.full_name: repo for repo in repositories}
        return [unique[name] for name in sorted(unique, key=str.casefold)]
