"""
Location check-in service for tracking family member locations.
"""

import datetime
import logging
import math
from typing import Optional

DEFAULT_PLACE_RADIUS_M = 150

try:
    from ...interfaces import ServiceResult
except ImportError:
    from interfaces import ServiceResult

from ..database_management.database_manager import DatabaseManager, DatabaseServiceMixin


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

    def resolve_place_name(self, lat: float, lon: float, user_id: str) -> Optional[str]:
        """Return the name of the nearest named place whose radius contains the point, or None. Nearest wins when places overlap."""
        result = self.get_named_places(user_id)
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
        user_id: str,
        family_member_id: str,
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

        location_name = self.resolve_place_name(latitude, longitude, user_id)
        if location_name is not None:
            self.logger.info("Resolved place name: %s", location_name)

        query = """
            INSERT INTO location_checkins 
            (user_id, family_member_id, timestamp, latitude, longitude, location_name, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        result = self.safe_update(
            query,
            (
                user_id,
                family_member_id,
                timestamp,
                latitude,
                longitude,
                location_name,
                notes,
            ),
        )

        if result.success:
            self.logger.info(
                "Check-in created for family member %s at (%s, %s)",
                family_member_id,
                latitude,
                longitude,
            )
            return ServiceResult.success_result(
                {
                    "user_id": user_id,
                    "family_member_id": family_member_id,
                    "timestamp": timestamp,
                    "latitude": latitude,
                    "longitude": longitude,
                    "location_name": location_name,
                    "notes": notes,
                }
            )
        return result

    def get_checkins(self, user_id: str) -> ServiceResult:
        """Get latest check-in per family member."""
        query = """
            SELECT c.id, c.user_id, c.family_member_id, c.timestamp,
                   c.latitude, c.longitude, c.location_name, c.notes,
                   fm.display_name as contact_name,
                   con.relationship,
                   fm.photo_filename
            FROM location_checkins c
            INNER JOIN (
                SELECT family_member_id, MAX(timestamp) as max_timestamp
                FROM location_checkins
                WHERE user_id = ?
                GROUP BY family_member_id
            ) latest ON c.family_member_id = latest.family_member_id
                    AND c.timestamp = latest.max_timestamp
            LEFT JOIN family_members fm ON c.family_member_id = fm.id
            LEFT JOIN contacts con ON fm.contact_id = con.id
            WHERE c.user_id = ?
            ORDER BY c.timestamp DESC
        """
        return self.safe_query(query, (user_id, user_id))

    def get_family_members(self, user_id: str) -> ServiceResult:
        """Return family members (for check-in dropdown). No user permissions in contacts."""
        query = """
            SELECT id, display_name, photo_filename, contact_id
            FROM family_members
            WHERE user_id = ?
            ORDER BY display_name
        """
        return self.safe_query(query, (user_id,))

    def get_named_places(self, user_id: Optional[str] = None) -> ServiceResult:
        """Return all family-wide named places for the user. location_id, location_name, gps_latitude, gps_longitude, radius_metres, safe, ordered by name."""
        query = """
            SELECT location_id, location_name, gps_latitude, gps_longitude,
                   COALESCE(radius_metres, ?) as radius_metres,
                   NULL as safe
            FROM named_places
            ORDER BY location_name
        """
        return self.safe_query(query, (DEFAULT_PLACE_RADIUS_M,))
