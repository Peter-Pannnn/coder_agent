"""SQLite-backed short-term memory for CoderAgent sessions."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SHORT_TERM_MEMORY_DB_PATH = Path("src/storage/short_term_memory.sqlite3")


@dataclass(frozen=True)
class ShortTermMemoryMessage:
    """One persisted short-term memory message."""

    role: str
    content: str
    created_at: str


class SQLiteShortTermMemory:
    """Persist short-term conversation messages in a local SQLite database."""

    def __init__(self, db_path: str | Path = DEFAULT_SHORT_TERM_MEMORY_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append one message to a session."""
        if role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'.")

        created_at = datetime.now(timezone.utc).isoformat()
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO short_term_memory_messages (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, created_at),
            )
            connection.commit()
        finally:
            connection.close()

    def load_recent(self, session_id: str, limit: int | None = 8) -> list[ShortTermMemoryMessage]:
        """Load recent messages for a session in chronological order.

        Passing None loads all messages for the session.
        """
        if limit is not None and limit <= 0:
            return []

        connection = self._connect()
        try:
            if limit is None:
                rows = connection.execute(
                    """
                    SELECT role, content, created_at
                    FROM short_term_memory_messages
                    WHERE session_id = ?
                    ORDER BY id ASC
                    """,
                    (session_id,),
                ).fetchall()
                return [
                    ShortTermMemoryMessage(role=row[0], content=row[1], created_at=row[2])
                    for row in rows
                ]

            rows = connection.execute(
                """
                SELECT role, content, created_at
                FROM short_term_memory_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        finally:
            connection.close()

        return [
            ShortTermMemoryMessage(role=row[0], content=row[1], created_at=row[2])
            for row in reversed(rows)
        ]

    def render_recent(self, session_id: str, limit: int | None = 8) -> str:
        """Render recent messages as prompt-friendly text."""
        messages = self.load_recent(session_id=session_id, limit=limit)
        return "\n".join(f"{message.role}: {message.content}" for message in messages)

    def clear(self, session_id: str) -> None:
        """Delete all messages for one session."""
        connection = self._connect()
        try:
            connection.execute(
                "DELETE FROM short_term_memory_messages WHERE session_id = ?",
                (session_id,),
            )
            connection.commit()
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS short_term_memory_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_short_term_memory_messages_session_id_id
                ON short_term_memory_messages (session_id, id)
                """
            )
            connection.commit()
        finally:
            connection.close()
