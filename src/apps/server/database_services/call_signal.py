"""
Incoming call signaling for kiosk page switching.
Stores short-lived call requests in the database.
"""

from ..database_manager import DatabaseManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult


class CallSignalService:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def request_call(
        self,
        family_circle_id: str,
        from_user_id: str,
        to_user_id: str,
        from_sendbird_user_id: str,
        from_display_name: str,
    ) -> ServiceResult:
        if not family_circle_id or not from_user_id or not to_user_id:
            return ServiceResult.error_result("family_circle_id, from_user_id, to_user_id required")
        r = self.db_manager.execute_insert(
            """
            INSERT INTO call_signals (
                family_circle_id,
                from_user_id,
                to_user_id,
                from_sendbird_user_id,
                from_display_name,
                status
            )
            VALUES (?, ?, ?, ?, ?, 'requested')
            """,
            (
                family_circle_id,
                from_user_id,
                to_user_id,
                from_sendbird_user_id or "",
                from_display_name or "",
            ),
        )
        if not r.success:
            return ServiceResult.error_result(r.error or "request_call failed")
        return ServiceResult.success_result({"call_id": r.data})

    def get_incoming_call(self, family_circle_id: str, to_user_id: str) -> ServiceResult:
        if not family_circle_id or not to_user_id:
            return ServiceResult.error_result("family_circle_id and to_user_id required")
        r = self.db_manager.execute_query(
            """
            SELECT
                id,
                from_user_id,
                from_sendbird_user_id,
                from_display_name,
                created_at
            FROM call_signals
            WHERE family_circle_id = ?
              AND to_user_id = ?
              AND status = 'requested'
            ORDER BY id DESC
            LIMIT 1
            """,
            (family_circle_id, to_user_id),
        )
        if not r.success:
            return ServiceResult.error_result(r.error or "incoming call query failed")
        if not r.data:
            return ServiceResult.success_result(None)
        row = r.data[0]
        return ServiceResult.success_result(
            {
                "call_id": row.get("id"),
                "from_user_id": row.get("from_user_id"),
                "from_sendbird_user_id": (row.get("from_sendbird_user_id") or "").strip(),
                "from_display_name": (row.get("from_display_name") or "").strip(),
                "created_at": row.get("created_at"),
            }
        )

    def acknowledge_call(self, call_id: int, to_user_id: str) -> ServiceResult:
        if not call_id or not to_user_id:
            return ServiceResult.error_result("call_id and to_user_id required")
        r = self.db_manager.execute_update(
            """
            UPDATE call_signals
            SET status = 'acknowledged'
            WHERE id = ? AND to_user_id = ? AND status = 'requested'
            """,
            (call_id, to_user_id),
        )
        if not r.success:
            return ServiceResult.error_result(r.error or "acknowledge failed")
        return ServiceResult.success_result({"updated": r.data})
