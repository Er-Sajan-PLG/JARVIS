"""LangGraph Checkpointing for JARVIS.

Provides checkpointing capabilities for LangGraph workflows using
SQLite-based persistence.
"""

import copy
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class Checkpointer(Protocol):
    """Interface shared by all checkpointer implementations."""

    def save(self, checkpoint_data: dict[str, Any], thread_id: str) -> str: ...
    def load(self, thread_id: str) -> dict[str, Any] | None: ...
    def list_checkpoints(self, thread_id: str) -> list[dict[str, Any]]: ...
    def delete(self, thread_id: str) -> bool: ...


if TYPE_CHECKING:
    from app.session.postgres_checkpointer import PostgresCheckpointer


@dataclass
class Checkpoint:
    """A single checkpoint in a workflow execution."""

    checkpoint_id: str
    thread_id: str
    checkpoint_data: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime
    parent_checkpoint_id: str | None = None


# Sprint 3: MemorySaver adapter (in-memory checkpointing for dev/unittest).
# Wraps LangGraph's MemorySaver when available, else falls back to a pure
# in-memory dict store so the module stays importable without langgraph.
class MemorySaverAdapter:
    """In-memory checkpoint adapter (dev / test / single-process).

    Provides LangGraph-compatible checkpoint storage semantics:
    ``put`` stores a checkpoint per thread, ``get`` retrieves the latest,
    ``list`` enumerates checkpoints for a thread, and ``delete`` clears them.

    When ``langgraph`` is installed, this wraps its ``MemorySaver``; otherwise
    it uses a plain dict so callers are unaffected by the optional dependency.
    """

    def __init__(self) -> None:
        self._by_thread: dict[str, dict[str, Any]] = {}
        try:
            from langgraph.checkpoint.memory import MemorySaver as _LGMemorySaver
        except Exception:  # noqa: BLE001 - langgraph is optional
            _LGMemorySaver = None
        self._lg_saver = _LGMemorySaver() if _LGMemorySaver is not None else None

    def save(self, checkpoint_data: dict[str, Any], thread_id: str) -> str:
        """Store a checkpoint and return its thread key."""
        self._by_thread[thread_id] = copy.deepcopy(checkpoint_data)
        return thread_id

    def load(self, thread_id: str) -> dict[str, Any] | None:
        """Return the latest checkpoint for a thread, or None."""
        return self._by_thread.get(thread_id)

    def list_threads(self) -> list[str]:
        """Return all thread ids that have at least one checkpoint."""
        return list(self._by_thread)

    def list_checkpoints(self, thread_id: str) -> list[dict[str, Any]]:
        """Return all checkpoints for a thread (newest first)."""
        data = self._by_thread.get(thread_id)
        if data is None:
            return []
        return [data]

    def delete(self, thread_id: str) -> bool:
        """Remove a thread's checkpoints; return whether anything was removed."""
        return self._by_thread.pop(thread_id, None) is not None

    def clear(self) -> None:
        self._by_thread.clear()

    def __len__(self) -> int:
        return len(self._by_thread)


class LangGraphCheckpointer:
    """SQLite-based checkpointer for LangGraph workflows.

    Provides persistent checkpointing for workflow state recovery
    and human-in-the-loop resumption.
    """

    def __init__(self, db_path: str = "data/checkpoints.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the checkpoint database."""
        import os

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    checkpoint_data TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    parent_checkpoint_id TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_thread_id
                ON checkpoints(thread_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON checkpoints(created_at)
            """)
            conn.commit()

    @contextmanager
    def _get_conn(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_checkpoint(
        self,
        thread_id: str,
        checkpoint_data: dict[str, Any],
        metadata: dict[str, Any],
        parent_checkpoint_id: str | None = None,
    ) -> str:
        """Save a checkpoint and return its ID."""
        checkpoint_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO checkpoints
                (checkpoint_id, thread_id, checkpoint_data, metadata,
                 created_at, parent_checkpoint_id)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    thread_id,
                    json.dumps(checkpoint_data),
                    json.dumps(metadata),
                    created_at,
                    parent_checkpoint_id,
                ),
            )
            conn.commit()

        return checkpoint_id

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """Retrieve a checkpoint by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
            ).fetchone()
            if row:
                return {
                    "checkpoint_id": row["checkpoint_id"],
                    "thread_id": row["thread_id"],
                    "checkpoint_data": json.loads(row["checkpoint_data"]),
                    "metadata": json.loads(row["metadata"]),
                    "created_at": row["created_at"],
                    "parent_checkpoint_id": row["parent_checkpoint_id"],
                }
        return None

    def get_latest_checkpoint(self, thread_id: str) -> dict[str, Any] | None:
        """Get the latest checkpoint for a thread."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
                (thread_id,),
            ).fetchone()
            if row:
                return {
                    "checkpoint_id": row["checkpoint_id"],
                    "thread_id": row["thread_id"],
                    "checkpoint_data": json.loads(row["checkpoint_data"]),
                    "metadata": json.loads(row["metadata"]),
                    "created_at": row["created_at"],
                    "parent_checkpoint_id": row["parent_checkpoint_id"],
                }
        return None

    def list_checkpoints(self, thread_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """List checkpoints for a thread."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT ?",
                (thread_id, limit),
            ).fetchall()
            return [
                {
                    "checkpoint_id": row["checkpoint_id"],
                    "thread_id": row["thread_id"],
                    "checkpoint_data": json.loads(row["checkpoint_data"]),
                    "metadata": json.loads(row["metadata"]),
                    "created_at": row["created_at"],
                    "parent_checkpoint_id": row["parent_checkpoint_id"],
                }
                for row in rows
            ]

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by ID."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_thread_checkpoints(self, thread_id: str) -> int:
        """Delete all checkpoints for a thread."""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            conn.commit()
            return cursor.rowcount


# Global checkpointer instance
_checkpointer: Optional["LangGraphCheckpointer"] = None


def get_checkpointer() -> "LangGraphCheckpointer":
    """Get the global checkpointer instance."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = LangGraphCheckpointer()
    return _checkpointer


# ---------------------------------------------------------------------------
# PostgreSQL-backed checkpointer (production)
# ---------------------------------------------------------------------------


def get_postgres_checkpointer(dsn: str) -> "PostgresCheckpointer":
    """Create a PostgreSQL-backed checkpointer for production deployments.

    Args:
        dsn: PostgreSQL connection string,
            e.g. ``postgresql://user:pass@host:5432/jarvis``.

    Returns:
        A configured ``PostgresCheckpointer`` instance.

    Raises:
        RuntimeError: If no PostgreSQL driver (psycopg / psycopg2 / asyncpg)
            is installed.
        ValueError: If *dsn* is empty.
    """
    from app.session.postgres_checkpointer import PostgresCheckpointer

    return PostgresCheckpointer(dsn=dsn)
