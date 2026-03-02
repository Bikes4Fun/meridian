"""
Centralized database management for Meridian.
Used by server only (container and app.py). Client gets data via API.
"""

import os
import sqlite3
import logging
from typing import List, Tuple
from contextlib import contextmanager

try:
    from ...shared.config import DatabaseConfig
    from ...shared.interfaces import ServiceResult
except ImportError:
    from shared.config import DatabaseConfig
    from shared.interfaces import ServiceResult


class DatabaseManager:
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(
                self.config.path, timeout=self.config.connection_timeout
            )
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            self.logger.error("Database connection error: %s", e)
            raise
        finally:
            if conn:
                conn.close()

    def execute_query(self, query: str, params: tuple = ()) -> ServiceResult:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()
                return ServiceResult.success_result([dict(row) for row in results])
        except sqlite3.Error as e:
            self.logger.error("Query execution failed: %s", e)
            return ServiceResult.error_result("Database query failed: %s" % e)

    def execute_update(self, query: str, params: tuple = ()) -> ServiceResult:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return ServiceResult.success_result(cursor.rowcount)
        except sqlite3.Error as e:
            self.logger.error("Update execution failed: %s", e)
            return ServiceResult.error_result("Database update failed: %s" % e)

    def execute_many(self, query: str, params_list: List[tuple]) -> ServiceResult:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return ServiceResult.success_result(cursor.rowcount)
        except sqlite3.Error as e:
            self.logger.error("Batch execution failed: %s", e)
            return ServiceResult.error_result("Database batch operation failed: %s" % e)

    def get_table_info(self, table_name: str) -> ServiceResult:
        return self.execute_query("PRAGMA table_info(%s)" % table_name)

    def get_table_count(self, table_name: str) -> ServiceResult:
        result = self.execute_query("SELECT COUNT(*) as count FROM %s" % table_name)
        if result.success and result.data:
            return ServiceResult.success_result(result.data[0]["count"])
        return result

    def create_database_schema(self) -> ServiceResult:
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if not os.path.exists(schema_path):
            return ServiceResult.error_result("Schema file not found: %s" % schema_path)
        try:
            with open(schema_path, "r") as f:
                schema_sql = f.read()
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()
            self.logger.info("Database schema created: %s", self.config.path)
            return ServiceResult.success_result(self.config.path)
        except Exception as e:
            self.logger.error("Schema creation failed: %s", e)
            return ServiceResult.error_result("Schema creation failed: %s" % e)

    def backup_database(self, backup_path: str) -> ServiceResult:
        if not self.config.backup_enabled:
            return ServiceResult.error_result("Backup not enabled")
        try:
            import shutil

            shutil.copy2(self.config.path, backup_path)
            self.logger.info("Database backed up to: %s", backup_path)
            return ServiceResult.success_result(backup_path)
        except Exception as e:
            self.logger.error("Backup failed: %s", e)
            return ServiceResult.error_result("Backup failed: %s" % e)


class DatabaseServiceMixin:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(self.__class__.__name__)

    def safe_query(self, query: str, params: tuple = ()) -> ServiceResult:
        return self.db_manager.execute_query(query, params)

    def safe_update(self, query: str, params: tuple = ()) -> ServiceResult:
        return self.db_manager.execute_update(query, params)
