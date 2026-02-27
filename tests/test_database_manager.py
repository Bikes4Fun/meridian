"""
Unit and integration tests for DatabaseManager.
"""
import pytest
import sqlite3
from lib.database_management.database_manager import DatabaseManager
from lib.config import DatabaseConfig
from lib.interfaces import ServiceResult


@pytest.mark.unit
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
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER, name TEXT)",
            ()
        )
        
        # Insert test data
        test_db_manager.execute_update(
            "INSERT INTO test_table (id, name) VALUES (?, ?)",
            (1, 'Test')
        )
        
        # Query the data
        result = test_db_manager.execute_query(
            "SELECT id, name FROM test_table WHERE id = ?",
            (1,)
        )
        
        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]['id'] == 1
        assert result.data[0]['name'] == 'Test'
    
    def test_execute_query_no_results(self, test_db_manager):
        """Test query with no results."""
        result = test_db_manager.execute_query(
            "SELECT * FROM contacts WHERE id = 'nonexistent'",
            ()
        )
        
        assert result.success is True
        assert result.data == []
    
    def test_execute_update_success(self, test_db_manager):
        """Test successful update execution."""
        # Create test table
        test_db_manager.execute_update(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER, name TEXT)",
            ()
        )
        
        result = test_db_manager.execute_update(
            "INSERT INTO test_table (id, name) VALUES (?, ?)",
            (1, 'Test')
        )
        
        assert result.success is True
        assert result.data == 1  # rowcount
    
    def test_execute_update_failure(self, test_db_manager):
        """Test update execution with invalid SQL."""
        result = test_db_manager.execute_update(
            "INSERT INTO nonexistent_table (id) VALUES (?)",
            (1,)
        )
        
        assert result.success is False
        assert 'error' in result.error.lower() or 'failed' in result.error.lower()
    
    def test_execute_many_success(self, test_db_manager):
        """Test batch execution."""
        # Create test table
        test_db_manager.execute_update(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER, name TEXT)",
            ()
        )
        
        params_list = [(1, 'Test1'), (2, 'Test2'), (3, 'Test3')]
        result = test_db_manager.execute_many(
            "INSERT INTO test_table (id, name) VALUES (?, ?)",
            params_list
        )
        
        assert result.success is True
        assert result.data == 3  # rowcount
        
        # Verify data was inserted
        query_result = test_db_manager.execute_query(
            "SELECT COUNT(*) as count FROM test_table",
            ()
        )
        assert query_result.data[0]['count'] == 3
    
    def test_get_table_info(self, test_db_manager):
        """Test getting table schema information."""
        result = test_db_manager.get_table_info('contacts')
        
        assert result.success is True
        assert len(result.data) > 0
        # Check that we have column information
        column_names = [row['name'] for row in result.data]
        assert 'id' in column_names
        assert 'display_name' in column_names
    
    def test_get_table_count(self, test_db_manager):
        """Test getting table row count."""
        result = test_db_manager.get_table_count('contacts')
        
        assert result.success is True
        assert isinstance(result.data, int)
        assert result.data >= 0
    
    def test_create_database_schema(self, test_db_config):
        """Test creating database schema."""
        manager = DatabaseManager(test_db_config)
        result = manager.create_database_schema()
        
        assert result.success is True
        
        # Verify schema was created by checking for tables
        tables_result = manager.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
            ()
        )
        assert tables_result.success is True
        table_names = [row['name'] for row in tables_result.data]
        assert 'contacts' in table_names
        assert 'medications' in table_names
        assert 'calendar_events' in table_names


@pytest.mark.integration
class TestDatabaseManagerIntegration:
    """Integration tests for DatabaseManager with real database operations."""
    
    def test_transaction_rollback_on_error(self, test_db_manager):
        """Test that transactions are properly handled."""
        # Create test table
        test_db_manager.execute_update(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)",
            ()
        )
        
        # Insert valid data
        test_db_manager.execute_update(
            "INSERT INTO test_table (name) VALUES (?)",
            ('Valid',)
        )
        
        # Try to insert invalid data (should fail)
        result = test_db_manager.execute_update(
            "INSERT INTO test_table (id, name) VALUES (?, ?)",
            ('invalid', 'Test')  # id should be integer
        )
        
        # The error should be caught and returned
        assert result.success is False
        
        # Verify the valid data is still there
        count_result = test_db_manager.get_table_count('test_table')
        assert count_result.data == 1
