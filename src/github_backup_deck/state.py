from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from github_backup_deck.config import state_dir
from github_backup_deck.models import BackupSummary

_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  destination TEXT NOT NULL,
  repositories_total INTEGER NOT NULL,
  repositories_ok INTEGER NOT NULL,
  repositories_failed INTEGER NOT NULL,
  summary_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS repository_runs (
  run_id TEXT NOT NULL,
  full_name TEXT NOT NULL,
  status TEXT NOT NULL,
  mirror_path TEXT NOT NULL,
  metadata_path TEXT NOT NULL,
  error TEXT,
  PRIMARY KEY (run_id, full_name),
  FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);
"""


class StateStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or state_dir() / "state.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript(_SCHEMA)
        return connection

    def record_summary(self, summary: BackupSummary) -> None:
        payload = json.dumps(summary.to_dict(), sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO runs
                (run_id, started_at, finished_at, destination, repositories_total,
                 repositories_ok, repositories_failed, summary_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.run_id,
                    summary.started_at,
                    summary.finished_at,
                    summary.destination,
                    summary.repositories_total,
                    summary.repositories_ok,
                    summary.repositories_failed,
                    payload,
                ),
            )
            connection.executemany(
                """
                INSERT OR REPLACE INTO repository_runs
                (run_id, full_name, status, mirror_path, metadata_path, error)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        summary.run_id,
                        result.full_name,
                        result.status,
                        result.mirror_path,
                        result.metadata_path,
                        result.error,
                    )
                    for result in summary.results
                ],
            )

    def latest_summary(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT summary_json FROM runs ORDER BY finished_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        value = json.loads(str(row["summary_json"]))
        return value if isinstance(value, dict) else None
