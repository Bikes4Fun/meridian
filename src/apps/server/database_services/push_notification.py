"""
Push notification service for Meridian.
Request family members to update location. Prepared for APNS (iOS) and FCM (Android).
"""

import logging

from ..database_manager import DatabaseManager

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Request location updates via push. Stub: logs; future: APNS/FCM."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def request_location_update(
        self, family_circle_id: str, requested_by_user_id: str
    ) -> ServiceResult:
        """Request all family members (except requester) to refresh location.
        Returns count of members notified. Stub: logs only; device tokens not yet stored.
        """
        query = """
            SELECT u.id, u.display_name
            FROM users u
            INNER JOIN user_family_circle ufc ON u.id = ufc.user_id
            WHERE ufc.family_circle_id = ? AND u.id != ?
            ORDER BY u.display_name
        """
        r = self.db_manager.execute_query(query, (family_circle_id, requested_by_user_id))
        if not r.success:
            return r
        members = r.data or []
        count = 0
        for m in members:
            uid = m.get("id")
            name = m.get("display_name") or "?"
            # Future: look up device_token from user_push_tokens, send via APNS/FCM
            logger.info(
                "Location update requested for user %s (%s) - push stub (APNS/FCM when ready)",
                uid,
                name,
            )
            count += 1
        return ServiceResult.success_result({"requested_count": count})
