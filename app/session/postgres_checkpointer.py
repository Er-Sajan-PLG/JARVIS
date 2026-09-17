"""PostgreSQL-backed checkpointer for JARVIS.

Provides ``PostgresCheckpointer`` — a PostgreSQL-backed checkpoint store
for production deployments where in-memory ``MemorySaverAdapter`` is
insufficient.  Falls back gracefully when neither ``psycopg`` nor
``asyncpg`` is installed.

Interface matches ``MemorySaverAdapter``:
    save(checkpoint_data, thread_id) -> str
    load(thread_id) -> dict | None
    list_checkpoints(thread_id) -> list
    delete(thread_id) -> bool
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, cast

logger = logging.getLogger(__name__)


def _try_import_psycopg() -> Any | None:
    """Try to import psycopg (v3), psycopg2, or asyncpg.

    Returns the module if available, else None.
    """
    try:
        import psycopg  # type: ignore[import-untyped]

        return psycopg
    except ImportError:
        pass
    try:
        import psycopg2  # type: ignore[import-untyped]

        return psycopg2
    except ImportError:
        pass
    try:
        import asyncpg  # type: ignore[import-untyped]

        return asyncpg
    except ImportError:
        pass
    return None


class PostgresCheckpointer:
    """PostgreSQL-backed checkpoint store.

    Creates a ``checkpoints`` table if it does not exist.  Uses either
    ``psycopg`` (v3), ``psycopg2``, or ``asyncpg`` depending on what is
    available.  When none are installed, the constructor raises
    ``RuntimeError``.

    Args:
        dsn: PostgreSQL connection string, e.g.
            ``postgresql://user:pass@host:5432/jarvis``.
    """

    def __init__(self, dsn: str) -> None:
        if not dsn:
            raise ValueError("PostgresCheckpointer requires a non-empty DSN")
        self.dsn = dsn
        driver = _try_import_psycopg()
        if driver is None:
            raise RuntimeError(
                "PostgresCheckpointer requires psycopg, psycopg2, or asyncpg. "
                "Install one of them, e.g. `pip install psycopg[binary]`."
            )
        self._driver = driver
        self._init_db()

    def _init_db(self) -> None:
        """Create the checkpoints table if it doesn't exist."""
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    checkpoint_data JSONB NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    parent_checkpoint_id TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id
                ON checkpoints(thread_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at
                ON checkpoints(created_at)
                """
            )
            conn.commit()

    @contextmanager
    def _get_conn(self):
        """Get a database connection."""
        driver = cast(Any, self._driver)
        conn = driver.connect(self.dsn)
        try:
            yield conn
        finally:
            conn.close()

    def _row_to_dict(self, row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
        """Convert a database row to a checkpoint dict."""
        d = dict(zip(columns, row, strict=False))
        return {
            "checkpoint_id": d["checkpoint_id"],
            "thread_id": d["thread_id"],
            "checkpoint_data": d["checkpoint_data"],
            "metadata": d["metadata"],
            "created_at": d["created_at"],
            "parent_checkpoint_id": d.get("parent_checkpoint_id"),
        }

    def save(self, checkpoint_data: dict[str, Any], thread_id: str) -> str:
        """Store a checkpoint and return its ID.

        Args:
            checkpoint_data: The checkpoint payload to persist.
            thread_id: The workflow/thread this checkpoint belongs to.

        Returns:
            The generated checkpoint ID (UUID string).
        """
        checkpoint_id = str(uuid.uuid4())
        metadata: dict[str, Any] = {}
        created_at = datetime.utcnow()

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO checkpoints
                (checkpoint_id, thread_id, checkpoint_data, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s)""",
                (
                    checkpoint_id,
                    thread_id,
                    json.dumps(checkpoint_data),
                    json.dumps(metadata),
                    created_at,
                ),
            )
            conn.commit()

        return checkpoint_id

    def load(self, thread_id: str) -> dict[str, Any] | None:
        """Return the latest checkpoint for a thread, or None.

        Args:
            thread_id: The workflow/thread to look up.

        Returns:
            The checkpoint dict, or ``None`` if no checkpoint exists.
        """
        with self._get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT checkpoint_id, thread_id, checkpoint_data,
                       metadata, created_at, parent_checkpoint_id
                    FROM checkpoints
                    WHERE thread_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1""",
                (thread_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            columns = [desc[0] for desc in cur.description]
            return self._row_to_dict(row, columns)

    def list_checkpoints(self, thread_id: str) -> list[dict[str, Any]]:
        """List all checkpoints for a thread, newest first.

        Args:
            thread_id: The workflow/thread to list.

        Returns:
            List of checkpoint dicts.
        """
        with self._get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT checkpoint_id, thread_id, checkpoint_data,
                       metadata, created_at, parent_checkpoint_id
                    FROM checkpoints
                    WHERE thread_id = %s
                    ORDER BY created_at DESC""",
                (thread_id,),
            )
            columns = [desc[0] for desc in cur.description]
            return [self._row_to_dict(row, columns) for row in cur.fetchall()]

    def delete(self, thread_id: str) -> bool:
        """Remove all checkpoints for a thread.

        Args:
            thread_id: The workflow/thread to delete.

        Returns:
            ``True`` if any checkpoints were removed, ``False`` otherwise.
        """
        with self._get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (thread_id,))
            deleted = cur.rowcount
            conn.commit()
        return deleted > 0
