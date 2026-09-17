"""Tests for PostgresCheckpointer.

These tests verify the contract compliance of the PostgreSQL-backed
checkpointer.  Since the PostgresCheckpointer requires a live PostgreSQL
database for full roundtrip tests, we test the unit-level behavior
(validation, graceful fallback) and skip integration tests that would
require a running database.

To run integration tests, set ``JARVIS_TEST_DATABASE_URL`` environment
variable to a PostgreSQL connection string.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. PostgresCheckpointer requires DSN
# ---------------------------------------------------------------------------


class TestPostgresCheckpointerRequiresDsn:
    def test_empty_dsn_raises_value_error(self):
        from app.session.postgres_checkpointer import PostgresCheckpointer

        with pytest.raises(ValueError, match="non-empty DSN"):
            PostgresCheckpointer(dsn="")

    def test_none_dsn_raises_value_error(self):
        from app.session.postgres_checkpointer import PostgresCheckpointer

        with pytest.raises(ValueError, match="non-empty DSN"):
            PostgresCheckpointer(dsn=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Graceful fallback when driver not installed (mock it)
# ---------------------------------------------------------------------------


class TestPostgresCheckpointerGracefulFallback:
    def test_raises_runtime_error_when_no_driver(self):
        """When psycopg / psycopg2 / asyncpg are not installed, raise RuntimeError."""
        from app.session.postgres_checkpointer import PostgresCheckpointer

        with patch(
            "app.session.postgres_checkpointer._try_import_psycopg",
            return_value=None,
        ):
            with pytest.raises(RuntimeError, match="psycopg.*psycopg2.*asyncpg"):
                PostgresCheckpointer(
                    dsn="postgresql://user:pass@localhost:5432/jarvis"
                )

    def test_error_message_mentions_install_command(self):
        """Error message should hint at installation command."""
        from app.session.postgres_checkpointer import PostgresCheckpointer

        with patch(
            "app.session.postgres_checkpointer._try_import_psycopg",
            return_value=None,
        ):
            with pytest.raises(RuntimeError, match="pip install"):
                PostgresCheckpointer(
                    dsn="postgresql://user:pass@localhost:5432/jarvis"
                )


# ---------------------------------------------------------------------------
# 3. Save and load roundtrip (requires database or mock)
# ---------------------------------------------------------------------------


class TestPostgresCheckpointerSaveLoad:
    def test_save_returns_checkpoint_id(self):
        """save() should return a UUID string."""
        from app.session.postgres_checkpointer import PostgresCheckpointer

        mock_driver = MagicMock()
        mock_conn = MagicMock()
        mock_driver.connect.return_value = mock_conn

        with patch(
            "app.session.postgres_checkpointer._try_import_psycopg",
            return_value=mock_driver,
        ):
            cp = PostgresCheckpointer(
                dsn="postgresql://user:pass@localhost:5432/jarvis"
            )
            # Reset mock calls from __init__'s _init_db
            mock_conn.reset_mock()
            mock_conn.cursor.return_value.__enter__ = MagicMock(
                return_value=MagicMock()
            )
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

            result = cp.save({"state": {"x": 1}}, "thread-1")
            assert isinstance(result, str)
            # Verify it's a valid UUID
            import uuid

            uuid.UUID(result)

    def test_load_returns_none_for_missing_thread(self):
        """load() should return None when thread has no checkpoints."""
        from app.session.postgres_checkpointer import PostgresCheckpointer

        mock_driver = MagicMock()
        mock_conn = MagicMock()
        mock_driver.connect.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "app.session.postgres_checkpointer._try_import_psycopg",
            return_value=mock_driver,
        ):
            cp = PostgresCheckpointer(
                dsn="postgresql://user:pass@localhost:5432/jarvis"
            )
            assert cp.load("nonexistent") is None


# ---------------------------------------------------------------------------
# 4. List checkpoints
# ---------------------------------------------------------------------------


class TestPostgresCheckpointerListCheckpoints:
    def test_list_checkpoints_returns_empty_for_missing(self):
        """list_checkpoints() should return empty list when thread has none."""
        from app.session.postgres_checkpointer import PostgresCheckpointer

        mock_driver = MagicMock()
        mock_conn = MagicMock()
        mock_driver.connect.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "app.session.postgres_checkpointer._try_import_psycopg",
            return_value=mock_driver,
        ):
            cp = PostgresCheckpointer(
                dsn="postgresql://user:pass@localhost:5432/jarvis"
            )
            result = cp.list_checkpoints("empty-thread")
            assert result == []


# ---------------------------------------------------------------------------
# 5. Delete checkpoints
# ---------------------------------------------------------------------------


class TestPostgresCheckpointerDelete:
    def test_delete_returns_false_when_nothing_deleted(self):
        """delete() should return False when no checkpoints exist."""
        from app.session.postgres_checkpointer import PostgresCheckpointer

        mock_driver = MagicMock()
        mock_conn = MagicMock()
        mock_driver.connect.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "app.session.postgres_checkpointer._try_import_psycopg",
            return_value=mock_driver,
        ):
            cp = PostgresCheckpointer(
                dsn="postgresql://user:pass@localhost:5432/jarvis"
            )
            assert cp.delete("empty-thread") is False

    def test_delete_returns_true_when_something_deleted(self):
        """delete() should return True when checkpoints were removed."""
        from app.session.postgres_checkpointer import PostgresCheckpointer

        mock_driver = MagicMock()
        mock_conn = MagicMock()
        mock_driver.connect.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 3
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            "app.session.postgres_checkpointer._try_import_psycopg",
            return_value=mock_driver,
        ):
            cp = PostgresCheckpointer(
                dsn="postgresql://user:pass@localhost:5432/jarvis"
            )
            assert cp.delete("thread-with-data") is True


# ---------------------------------------------------------------------------
# 6. Factory function
# ---------------------------------------------------------------------------


class TestGetPostgresCheckpointerFactory:
    def test_factory_creates_instance(self):
        """get_postgres_checkpointer() should return a PostgresCheckpointer."""
        from app.session.checkpointer import get_postgres_checkpointer

        mock_driver = MagicMock()
        mock_conn = MagicMock()
        mock_driver.connect.return_value = mock_conn

        with patch(
            "app.session.postgres_checkpointer._try_import_psycopg",
            return_value=mock_driver,
        ):
            cp = get_postgres_checkpointer(
                dsn="postgresql://user:pass@localhost:5432/jarvis"
            )
            from app.session.postgres_checkpointer import PostgresCheckpointer

            assert isinstance(cp, PostgresCheckpointer)


# ---------------------------------------------------------------------------
# 7. Integration test (skipped unless JARVIS_TEST_DATABASE_URL is set)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("JARVIS_TEST_DATABASE_URL"),
    reason="Set JARVIS_TEST_DATABASE_URL to run integration tests",
)
class TestPostgresCheckpointerIntegration:
    def test_integration_save_load_roundtrip(self):
        from app.session.checkpointer import get_postgres_checkpointer

        dsn = os.environ["JARVIS_TEST_DATABASE_URL"]
        cp = get_postgres_checkpointer(dsn)
        test_thread = f"test-{os.urandom(4).hex()}"

        try:
            checkpoint_data = {"state": {"counter": 42, "items": ["a", "b", "c"]}}
            cp.save(checkpoint_data, test_thread)

            loaded = cp.load(test_thread)
            assert loaded is not None
            assert loaded["checkpoint_data"]["state"]["counter"] == 42
            assert loaded["checkpoint_data"]["state"]["items"] == ["a", "b", "c"]
        finally:
            cp.delete(test_thread)

    def test_integration_list_and_delete(self):
        from app.session.checkpointer import get_postgres_checkpointer

        dsn = os.environ["JARVIS_TEST_DATABASE_URL"]
        cp = get_postgres_checkpointer(dsn)
        test_thread = f"test-list-{os.urandom(4).hex()}"

        try:
            cp.save({"v": 1}, test_thread)
            cp.save({"v": 2}, test_thread)

            checkpoints = cp.list_checkpoints(test_thread)
            assert len(checkpoints) >= 2

            assert cp.delete(test_thread) is True
            assert cp.load(test_thread) is None
            assert cp.list_checkpoints(test_thread) == []
        finally:
            # Ensure cleanup even if assertions fail
            try:
                cp.delete(test_thread)
            except Exception:
                pass
