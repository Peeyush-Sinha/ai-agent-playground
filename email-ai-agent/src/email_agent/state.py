"""Local SQLite state for duplicate prevention."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import DraftDecision


class StateStore:
    """Stores which Gmail messages have already been processed."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_messages (
                    gmail_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    draft_id TEXT,
                    subject TEXT,
                    decision_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_processed_created_at ON processed_messages(created_at)"
            )

    def has_processed(self, gmail_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_messages WHERE gmail_id = ? LIMIT 1",
                (gmail_id,),
            ).fetchone()
        return row is not None

    def mark_processed(
        self,
        *,
        gmail_id: str,
        thread_id: str,
        draft_id: str | None,
        subject: str,
        decision: DraftDecision,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processed_messages
                (gmail_id, thread_id, draft_id, subject, decision_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    gmail_id,
                    thread_id,
                    draft_id,
                    subject,
                    json.dumps(asdict(decision), ensure_ascii=False),
                ),
            )

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT gmail_id, thread_id, draft_id, subject, decision_json, created_at
                FROM processed_messages
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
