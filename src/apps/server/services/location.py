"""
Location check-in service for tracking family member locations.
"""

import datetime
import logging
import math
from typing import Optional

DEFAULT_PLACE_RADIUS_M = 150

try:
    from ....shared.interfaces import ServiceResult
except ImportError:
    from shared.interfaces import ServiceResult

from ..database import DatabaseManager, DatabaseServiceMixin


class LocationService(DatabaseServiceMixin):
    """Service for managing location check-ins."""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager)
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return distance in metres between two WGS84 points. (lat1,lon1) and (lat2,lon2). Earth radius 6,371,000 m."""
        r = 6_371_000  # Earth radius in metres
        phi1 = math.radians(lat1)  # user check-in latitude
        phi2 = math.radians(lat2)  # named place center latitude
        dphi = math.radians(lat2 - lat1)  # latitude difference
        dlam = math.radians(lon2 - lon1)  # longitude difference

        # Haversine: combine lat/lon contributions to get angular distance
        lat_to_ang = math.sin(dphi / 2) ** 2
        lon_lat_scale = math.cos(phi1) * math.cos(
            phi2
        )  # scales lon by how far N/S the points are
        lon_to_ang = math.sin(dlam / 2) ** 2
        ang_combined = lat_to_ang + lon_lat_scale * lon_to_ang

        x = math.sqrt(ang_combined)
        y = math.sqrt(1 - ang_combined)

        # angular distance in radians
        ang_dist = 2 * math.atan2(x, y)

        # angular dist (radians) × Earth radius → arc length in metres
        return r * ang_dist

    def resolve_place_name(self, lat: float, lon: float, family_circle_id: str) -> Optional[str]:
        """Return the name of the nearest named place whose radius contains the point, or None. Nearest wins when places overlap."""
        result = self.get_named_places(family_circle_id)
        if not result.success or not result.data:
            return None
        nearest_name = None
        nearest_dist = float("inf")
        for row in result.data:

            # cords of place center: "Eleanor Home"
            plat = row.get("gps_latitude")
            plon = row.get("gps_longitude")

            place_radius = row.get("radius_metres", DEFAULT_PLACE_RADIUS_M)

            if plat is None or plon is None:
                continue

            dist_between = self._haversine_metres(lat, lon, plat, plon)

            if dist_between <= place_radius and dist_between < nearest_dist:
                nearest_dist = dist_between
                nearest_name = row.get("location_name")
        return nearest_name

    def create_checkin(
        self,
        family_circle_id: str,
        user_id: str,
        latitude: float,
        longitude: float,
        notes: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> ServiceResult:
        """Create a new location check-in.
        location_name: always resolved from GPS (never from client).
        notes: user's message to family; default 'Checked in via web' when empty."""
        if timestamp is None:
            timestamp = datetime.datetime.now().isoformat()

        location_name = self.resolve_place_name(latitude, longitude, family_circle_id)
        if location_name is not None:
            self.logger.info("Resolved place name: %s", location_name)

        query = """
            INSERT INTO location_checkins 
            (family_circle_id, user_id, timestamp, latitude, longitude, location_name, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        result = self.safe_update(
            query,
            (
                family_circle_id,
                user_id,
                timestamp,
                latitude,
                longitude,
                location_name,
                notes,
            ),
        )

        if result.success:
            self.logger.info(
                "Check-in created for user %s at (%s, %s)",
                user_id,
                latitude,
                longitude,
            )
            return ServiceResult.success_result(
                {
                    "family_circle_id": family_circle_id,
                    "user_id": user_id,
                    "timestamp": timestamp,
                    "latitude": latitude,
                    "longitude": longitude,
                    "location_name": location_name,
                    "notes": notes,
                }
            )
        return result

    def get_checkins(self, family_circle_id: str) -> ServiceResult:
        """Get latest check-in per user in the family."""
        query = """
            SELECT c.id, c.family_circle_id, c.user_id, c.timestamp,
                   c.latitude, c.longitude, c.location_name, c.notes,
                   u.display_name as contact_name,
                   u.photo_filename
            FROM location_checkins c
            INNER JOIN (
                SELECT user_id, MAX(timestamp) as max_timestamp
                FROM location_checkins
                WHERE family_circle_id = ?
                GROUP BY user_id
            ) latest ON c.user_id = latest.user_id
                    AND c.timestamp = latest.max_timestamp
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.family_circle_id = ?
            ORDER BY c.timestamp DESC
        """
        return self.safe_query(query, (family_circle_id, family_circle_id))

    def get_family_members(self, family_circle_id: str) -> ServiceResult:
        """Return users in the family (for check-in dropdown)."""
        query = """
            SELECT u.id, u.display_name, u.photo_filename
            FROM users u
            INNER JOIN user_family_circle ufc ON u.id = ufc.user_id
            WHERE ufc.family_circle_id = ?
            ORDER BY u.display_name
        """
        return self.safe_query(query, (family_circle_id,))

    def get_named_places(self, family_circle_id: Optional[str] = None) -> ServiceResult:
        """Return all family-wide named places. location_id, location_name, gps_latitude, gps_longitude, radius_metres, safe, ordered by name."""
        if not family_circle_id:
            return self.safe_query("SELECT 1 WHERE 0", ())
        query = """
            SELECT location_id, location_name, gps_latitude, gps_longitude,
                   COALESCE(radius_metres, ?) as radius_metres,
                   NULL as safe
            FROM named_places
            WHERE family_circle_id = ?
            ORDER BY location_name
        """
        return self.safe_query(query, (DEFAULT_PLACE_RADIUS_M, family_circle_id))
