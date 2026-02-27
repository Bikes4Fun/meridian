# Sub-Issue: Web Map — Place Circles, Labels & Smart Marker Display

**Parent milestone:** Named Places for Family Location Tracking  
**Depends on:** TV map complete (family markers, check-ins, APIs)  

## Overview

Web-based map (`map.html`) for caregivers to view family locations. Named places as radius circles on the map, labels, sidebar with fly-to, and smart client-side place matching for check-ins. Complements the TV map.

## Changes

### `webapp/web_client/map.html` (new file)

- On load and every 60 s: fetch `GET /api/location/places` and `GET /api/location/latest` in parallel using `Promise.all`
- For each named place: render `L.circle` at `[gps_latitude, gps_longitude]` with `radius: radius_metres`, low `fillOpacity` (~0.08), and a non-interactive `L.divIcon` text label pinned at the centre
- Add a "Named Places" section to the sidebar: list each place name and radius in metres; clicking flies the map to that place at zoom 17
- Implement `haversineMetres` in JS and run client-side place matching for each check-in (so older check-ins without a stored `location_name` still resolve)
- Person popups: show matched place name as a styled badge above the person's name
- Sidebar cards: use the matched place name as the primary location line, falling back to raw `location_name` then coordinates
- Status bar: show both member count and named place count

### Server

- Add `GET /map` route to serve `map.html` (and `map.js` if separate)

## Acceptance Criteria

- [ ] Each named place appears as a circle on the map at the correct radius
- [ ] A family member whose coordinates fall within a place's circle shows that place name in their popup badge and sidebar card
- [ ] A family member outside all circles shows their raw location or coordinates
- [ ] Clicking a place in the sidebar flies to it; clicking a person card flies to their marker and opens their popup
- [ ] Named places load in parallel with check-ins — no sequential waterfall
