# Sub-Issue 3 (Revised): TV Map — Family Markers, Photos & Check-In Display

**Parent milestone:** Named Places for Family Location Tracking  
**Depends on:** Sub-Issue 2  

## Overview

TV-based family map on the Kivy app showing where family members have checked in. Custom photo markers per family member. Named places and check-ins displayed as text. Remote check-in from web/phone.

## Completed Changes

### TV App (Kivy)

**`lib/display/screens.py`**
- `create_family_screen()` — Family Locations screen with map container
- Lazy-load `MapView` on screen enter (avoids black screen in ScreenManager)
- Fetch check-ins via `location_service.get_checkins()`
- For each check-in: add `CustomMarker` with photo (cropped to circle) or `MapMarker` if no photo
- `_crop_image_to_circle()` — crop profile images to circle for Life360-style markers

**`lib/display/widgets.py`**
- `create_family_locations_widget()` — title, two-column layout, map
- `_create_family_possible_places_block()` — list named places (name + coords) from `GET /api/location/places`
- `_create_family_checkins_block()` — list latest check-in per member (name, location, time) from `GET /api/location/latest`
- `_create_family_future_map_block()` — map container with fixed lat/lon/zoom params

### APIs (existing)
- `GET /api/location/places` — named places with gps_latitude, gps_longitude, radius_metres
- `GET /api/location/latest` — latest check-in per family member
- `POST /api/location/checkin` — create check-in (used by web client)

### Web Check-In
- `webapp/web_client/checkin.html` + `checkin.js` — family can check in from any device via real URL (not just local network)
- Serves `GET /checkin`, `GET /checkin.js`
- Uses `navigator.geolocation` → `POST /api/location/checkin`

### Other Fixes (this branch)
- Fixed contacts and family/users being combined
- Fixed server resetting behavior
- Replaced excessive prints with debug loggers

## Acceptance Criteria (Met)

- [x] Family members appear as markers on the TV map
- [x] Markers show family photo (cropped to circle) when available
- [x] Named places displayed as text list
- [x] Check-ins displayed as text list (name, location, time)
- [x] Remote check-in works from other devices via real URL
- [x] Map loads lazily on screen enter
