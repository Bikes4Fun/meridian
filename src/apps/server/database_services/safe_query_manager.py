"""
Centralized database management for Meridian.
Used by server only (db_service_registry and api.py). Client gets data via API.
"""

import os
import sqlite3
import logging
from typing import List, Tuple
from contextlib import contextmanager

try:
    from ....shared.config import DatabaseConfig
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.config import DatabaseConfig
    from shared.interfaces import ServiceResult

_KNOWN_TABLE_NAMES = frozenset(
    {
        "users",
        "family_circles",
        "family_memberships",
        "family_permissions",
        "contacts",
        "medication_time_templates",
        "medication_times",
        "medications",
        "medication_to_time",
        "allergies",
        "conditions",
        "care_recipients",
        "ice_contact_roles",
        "ice_profile",
        "calendar_events",
        "named_places",
        "location_checkins",
        "user_push_tokens",
        "call_signals",
        "kiosk_emergency_alerts",
        "care_recipient_documents",
    }
)

# Columns that may be missing on databases created before these were added.
# Format: (table, column, definition)
_COLUMN_MIGRATIONS = [
    ("care_recipients", "medical_dni_status", "TEXT"),
    ("care_recipients", "medical_nutrition_status", "TEXT"),
    ("care_recipients", "devices_notes", "TEXT"),
    ("care_recipients", "brief_history", "TEXT"),
    ("care_recipients", "other_notes", "TEXT"),
    ("care_recipients", "polst_dnr_signed", "INTEGER DEFAULT 0"),
    ("care_recipients", "polst_dni_signed", "INTEGER DEFAULT 0"),
    ("care_recipients", "polst_nutrition_signed", "INTEGER DEFAULT 0"),
    ("allergies", "reaction", "TEXT"),
]


class QueryManager:
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
            return ServiceResult.error_result("Database query failed")

    def execute_update(self, query: str, params: tuple = ()) -> ServiceResult:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return ServiceResult.success_result(cursor.rowcount)
        except sqlite3.Error as e:
            self.logger.error("Update execution failed: %s", e)
            return ServiceResult.error_result("Database update failed")

    def execute_insert(self, query: str, params: tuple = ()) -> ServiceResult:
        """Run INSERT, return lastrowid on success."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return ServiceResult.success_result(cursor.lastrowid)
        except sqlite3.Error as e:
            self.logger.error("Insert execution failed: %s", e)
            return ServiceResult.error_result("Database insert failed")

    def execute_many(self, query: str, params_list: List[tuple]) -> ServiceResult:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return ServiceResult.success_result(cursor.rowcount)
        except sqlite3.Error as e:
            self.logger.error("Batch execution failed: %s", e)
            return ServiceResult.error_result("Database batch operation failed")

    def get_table_info(self, table_name: str) -> ServiceResult:
        if table_name not in _KNOWN_TABLE_NAMES:
            return ServiceResult.error_result("invalid table name")
        return self.execute_query(f'PRAGMA table_info("{table_name}")')

    def get_table_count(self, table_name: str) -> ServiceResult:
        if table_name not in _KNOWN_TABLE_NAMES:
            return ServiceResult.error_result("invalid table name")
        result = self.execute_query(f'SELECT COUNT(*) as count FROM "{table_name}"')
        if result.success and result.data:
            return ServiceResult.success_result(result.data[0]["count"])
        return result

    def _apply_column_migrations(self, conn) -> None:
        """Add any missing columns to existing tables (forward-only, never removes)."""
        cursor = conn.cursor()
        for table, column, definition in _COLUMN_MIGRATIONS:
            cursor.execute(f'PRAGMA table_info("{table}")')
            existing = {row[1] for row in cursor.fetchall()}
            if column not in existing:
                cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')
        conn.commit()

    def create_database_schema(self) -> ServiceResult:
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if not os.path.exists(schema_path):
            return ServiceResult.error_result(f"Schema file not found: {schema_path}")
        try:
            with open(schema_path, "r") as f:
                schema_sql = f.read()
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()
                self._apply_column_migrations(conn)
            self.logger.info("Database schema created: %s", self.config.path)
            return ServiceResult.success_result(self.config.path)
        except Exception as e:
            self.logger.error("Schema creation failed: %s", e)
            return ServiceResult.error_result("Schema creation failed")

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
            return ServiceResult.error_result("Backup failed")
