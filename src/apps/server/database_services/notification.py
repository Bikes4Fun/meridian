"""
Push notification service for Meridian.
Request family members to update location. APNS when configured; stub otherwise.
"""

import logging
import os

from .safe_query_manager import QueryManager

try:
    from ....shared.interfaces import ServiceResult
    from ....shared.config import (
        get_apns_auth_key_path,
        get_apns_bundle_id,
        get_apns_key_id,
        get_apns_team_id,
        get_apns_use_sandbox,
    )
except ImportError:
    from shared.interfaces import ServiceResult
    from shared.config import (
        get_apns_auth_key_path,
        get_apns_bundle_id,
        get_apns_key_id,
        get_apns_team_id,
        get_apns_use_sandbox,
    )

logger = logging.getLogger(__name__)


def _send_apns(
    device_tokens: list[str],
    family_circle_id: str,
    auth_key_path: str,
    key_id: str,
    team_id: str,
    bundle_id: str,
    use_sandbox: bool,
) -> int:
    """Send APNs to each token. Returns count sent successfully."""
    try:
        from pyapns_client import (
            APNSClient,
            IOSNotification,
            IOSPayload,
            IOSPayloadAlert,
        )
    except ImportError as e:
        logger.warning("pyapns_client not installed: %s", e)
        return 0
    auth_key_path = os.path.abspath(auth_key_path)
    if not os.path.isfile(auth_key_path):
        logger.warning("APNs auth key not found: %s", auth_key_path)
        return 0
    mode = APNSClient.MODE_DEV if use_sandbox else APNSClient.MODE_PROD
    sent = 0
    try:
        client = APNSClient(
            mode=mode,
            root_cert_path=None,
            auth_key_path=auth_key_path,
            auth_key_id=key_id,
            team_id=team_id,
        )
        alert = IOSPayloadAlert(
            title="Where is everyone?",
            body="Your family wants to know your location.",
        )
        payload = IOSPayload(
            alert=alert,
            custom={
                "meridian_action": "location_refresh_requested",
                "family_circle_id": family_circle_id,
            },
        )
        notification = IOSNotification(payload=payload, topic=bundle_id)
        for token in device_tokens:
            try:
                client.push(notification=notification, device_token=token)
                sent += 1
            except Exception as e:
                logger.debug("APNs push failed for token %s...: %s", token[:8], e)
        client.close()
    except Exception as e:
        logger.warning("APNs send failed: %s", e)
    return sent


class PushNotificationService:
    """Request location updates via push. APNS when configured; stub otherwise."""

    def __init__(self, db_manager: QueryManager):
        self.db_manager = db_manager

    def request_location_update(
        self, family_circle_id: str, requested_by_user_id: str
    ) -> ServiceResult:
        """Request all family members (except requester) to refresh location.
        Looks up ios device tokens, sends via APNs when configured.
        """
        query = """
            SELECT u.id, u.display_name, upt.device_token
            FROM users u
            INNER JOIN family_memberships ufc ON u.id = ufc.user_id
            LEFT JOIN user_push_tokens upt ON upt.user_id = u.id AND upt.platform = 'ios'
            WHERE ufc.family_circle_id = ? AND u.id != ?
            ORDER BY u.display_name
        """
        r = self.db_manager.execute_query(
            query, (family_circle_id, requested_by_user_id)
        )
        if not r.success:
            return r
        members = r.data or []
        device_tokens = list(
            {m["device_token"] for m in members if m.get("device_token")}
        )
        seen_ids = set()
        auth_path = get_apns_auth_key_path()
        key_id = get_apns_key_id()
        team_id = get_apns_team_id()
        if auth_path and key_id and team_id and device_tokens:
            count = _send_apns(
                device_tokens,
                family_circle_id,
                auth_path,
                key_id,
                team_id,
                get_apns_bundle_id(),
                get_apns_use_sandbox(),
            )
            for m in members:
                if m.get("id") in seen_ids:
                    continue
                seen_ids.add(m.get("id"))
                uid = m.get("id")
                name = m.get("display_name") or "?"
                logger.info(
                    "Location update sent for user %s (%s)",
                    uid,
                    name,
                )
        else:
            count = 0
            for m in members:
                if m.get("id") in seen_ids:
                    continue
                seen_ids.add(m.get("id"))
                uid = m.get("id")
                name = m.get("display_name") or "?"
                logger.info(
                    "Location update requested for user %s (%s) - stub (set APNS_* env for real push)",
                    uid,
                    name,
                )
                count += 1
        return ServiceResult.success_result({"requested_count": count})

    def register_device_token(
        self, user_id: str, device_token: str, platform: str
    ) -> ServiceResult:
        """Store device token for push. Upserts by (user_id, device_token)."""
        if platform not in ("ios", "android"):
            return ServiceResult.error_result("platform must be ios or android")
        if not device_token or not user_id:
            return ServiceResult.error_result("user_id and device_token required")
        r = self.db_manager.execute_update(
            """
            INSERT INTO user_push_tokens (user_id, device_token, platform)
            VALUES (?, ?, ?)
            ON CONFLICT (user_id, device_token) DO UPDATE SET platform = ?
            """,
            (user_id, device_token, platform, platform),
        )
        return r if r.success else ServiceResult.error_result(r.error or "unknown")
