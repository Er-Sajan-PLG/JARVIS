"""LangGraph Checkpointing for JARVIS.

Provides checkpointing capabilities for LangGraph workflows using
SQLite-based persistence.
"""

import sqlite3
import json
import uuid
from typing import Any, Optional, List, Dict
from datetime import datetime
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class Checkpoint:
    """A single checkpoint in a workflow execution."""
    checkpoint_id: str
    thread_id: str
    checkpoint_data: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime
    parent_checkpoint_id: Optional[str] = None


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
        checkpoint_data: Dict[str, Any],
        metadata: Dict[str, Any],
        parent_checkpoint_id: Optional[str] = None
    ) -> str:
        """Save a checkpoint and return its ID."""
        checkpoint_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO checkpoints 
                (checkpoint_id, thread_id, checkpoint_data, metadata, created_at, parent_checkpoint_id)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    thread_id,
                    json.dumps(checkpoint_data),
                    json.dumps(metadata),
                    created_at,
                    parent_checkpoint_id
                )
            )
            conn.commit()
        
        return checkpoint_id
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a checkpoint by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,)
            ).fetchone()
            if row:
                return {
                    "checkpoint_id": row["checkpoint_id"],
                    "thread_id": row["thread_id"],
                    "checkpoint_data": json.loads(row["checkpoint_data"]),
                    "metadata": json.loads(row["metadata"]),
                    "created_at": row["created_at"],
                    "parent_checkpoint_id": row["parent_checkpoint_id"]
                }
        return None
    
    def get_latest_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest checkpoint for a thread."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1",
                (thread_id,)
            ).fetchone()
            if row:
                return {
                    "checkpoint_id": row["checkpoint_id"],
                    "thread_id": row["thread_id"],
                    "checkpoint_data": json.loads(row["checkpoint_data"]),
                    "metadata": json.loads(row["metadata"]),
                    "created_at": row["created_at"],
                    "parent_checkpoint_id": row["parent_checkpoint_id"]
                }
        return None
    
    def list_checkpoints(self, thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List checkpoints for a thread."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY created_at DESC LIMIT ?",
                (thread_id, limit)
            ).fetchall()
            return [
                {
                    "checkpoint_id": row["checkpoint_id"],
                    "thread_id": row["thread_id"],
                    "checkpoint_data": json.loads(row["checkpoint_data"]),
                    "metadata": json.loads(row["metadata"]),
                    "created_at": row["created_at"],
                    "parent_checkpoint_id": row["parent_checkpoint_id"]
                }
                for row in rows
            ]
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by ID."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_thread_checkpoints(self, thread_id: str) -> int:
        """Delete all checkpoints for a thread."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE thread_id = ?",
                (thread_id,)
            )
            conn.commit()
            return cursor.rowcount


# Global checkpointer instance
_checkpointer: Optional['LangGraphCheckpointer'] = None


def get_checkpointer() -> 'LangGraphCheckpointer':
    """Get the global checkpointer instance."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = LangGraphCheckpointer()
    return _checkpointer