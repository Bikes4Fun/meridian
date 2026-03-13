"""
Integration tests for DatabaseManager (DB required). Infrastructure: schema, persistence, invalid path.
"""

import os
import pytest
from apps.server.database import DatabaseManager
from shared.config import DatabaseConfig
from shared.interfaces import ServiceResult


@pytest.mark.integration
class TestDatabaseManager:
    """Test cases for DatabaseManager."""

    def test_connection_success(self, test_db_manager):
        """Test successful database connection."""
        with test_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

    def test_execute_query_success(self, test_db_manager):
        """Test successful query execution."""
        # First create a test table
        test_db_manager.execute_update(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER, name TEXT)", ()
        )

        # Insert test data
        test_db_manager.execute_update(
            "INSERT INTO test_table (id, name) VALUES (?, ?)", (1, "Test")
        )

        # Query the data
        result = test_db_manager.execute_query(
            "SELECT id, name FROM test_table WHERE id = ?", (1,)
        )

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["id"] == 1
        assert result.data[0]["name"] == "Test"

    def test_execute_query_no_results(self, test_db_manager):
        """Test query with no results."""
        result = test_db_manager.execute_query(
            "SELECT * FROM contacts WHERE id = 'nonexistent'", ()
        )

        assert result.success is True
        assert result.data == []

    def test_execute_update_success(self, test_db_manager):
        """Test successful update execution."""
        # Create test table
        test_db_manager.execute_update(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER, name TEXT)", ()
        )

        result = test_db_manager.execute_update(
            "INSERT INTO test_table (id, name) VALUES (?, ?)", (1, "Test")
        )

        assert result.success is True
        assert result.data == 1  # rowcount

    def test_execute_update_failure(self, test_db_manager):
        """Test update execution with invalid SQL."""
        result = test_db_manager.execute_update(
            "INSERT INTO nonexistent_table (id) VALUES (?)", (1,)
        )

        assert result.success is False
        assert "error" in result.error.lower() or "failed" in result.error.lower()

    def test_execute_many_success(self, test_db_manager):
        """Test batch execution."""
        # Create test table
        test_db_manager.execute_update(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER, name TEXT)", ()
        )

        params_list = [(1, "Test1"), (2, "Test2"), (3, "Test3")]
        result = test_db_manager.execute_many(
            "INSERT INTO test_table (id, name) VALUES (?, ?)", params_list
        )

        assert result.success is True
        assert result.data == 3  # rowcount

        # Verify data was inserted
        query_result = test_db_manager.execute_query(
            "SELECT COUNT(*) as count FROM test_table", ()
        )
        assert query_result.data[0]["count"] == 3

    def test_db_persistence_write_then_read(self, test_db_manager):
        """Write then read back in same test; proves writes stick."""
        test_db_manager.execute_update(
            "INSERT OR REPLACE INTO family_circles (id) VALUES (?)",
            ("persist_test_fc",),
        )
        r = test_db_manager.execute_query(
            "SELECT id FROM family_circles WHERE id = ?",
            ("persist_test_fc",),
        )
        assert r.success is True
        assert len(r.data) == 1
        assert r.data[0]["id"] == "persist_test_fc"

    def test_fresh_db_schema_queryable(self, test_db_config):
        """Fresh DB (schema only, no seed): tables exist and are queryable."""
        manager = DatabaseManager(test_db_config)
        result = manager.create_database_schema()
        assert result.success is True
        r = manager.execute_query("SELECT id FROM family_circles LIMIT 1", ())
        assert r.success is True
        assert r.data is not None
        r2 = manager.execute_query("SELECT id FROM contacts LIMIT 1", ())
        assert r2.success is True

    def test_invalid_db_path_fails(self, test_db_config):
        """Invalid DB path: DatabaseManager.create_database_schema returns error with 'Schema creation failed'."""
        config = DatabaseConfig(
            path=os.path.join(os.path.sep, "nonexistent_dir_xyz", "db.db"),
            create_if_missing=True,
            backup_enabled=False,
            connection_timeout=1,
        )
        manager = DatabaseManager(config)
        result = manager.create_database_schema()
        assert result.success is False
        assert result.error
        assert "Schema creation failed" in result.error

    def test_create_database_schema(self, test_db_config):
        """Test creating database schema."""
        manager = DatabaseManager(test_db_config)
        result = manager.create_database_schema()

        assert result.success is True

        # Verify schema was created by checking for tables
        tables_result = manager.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'", ()
        )
        assert tables_result.success is True
        table_names = [row["name"] for row in tables_result.data]
        assert "contacts" in table_names
        assert "medications" in table_names
        assert "calendar_events" in table_names


@pytest.mark.integration
class TestDatabaseManagerIntegration:
    """Integration tests for DatabaseManager with real database operations."""

    def test_transaction_rollback_on_error(self, test_db_manager):
        """Test that transactions are properly handled."""
        # Create test table
        test_db_manager.execute_update(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)",
            (),
        )

        # Insert valid data
        test_db_manager.execute_update(
            "INSERT INTO test_table (name) VALUES (?)", ("Valid",)
        )

        # Try to insert invalid data (should fail)
        result = test_db_manager.execute_update(
            "INSERT INTO test_table (id, name) VALUES (?, ?)",
            ("invalid", "Test"),  # id should be integer
        )

        # The error should be caught and returned
        assert result.success is False

        # Verify the valid data is still there
        count_result = test_db_manager.execute_query(
            "SELECT COUNT(*) as n FROM test_table", ()
        )
        assert count_result.success and count_result.data[0]["n"] == 1
