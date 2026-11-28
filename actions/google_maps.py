"""
JARVIS H3.2 — Google Maps Action Adapter
Provides voice and assistant control for Google Maps Platform APIs.
Thread-safe for UI calls via player.
"""

from typing import Dict, Any, Optional
from core.google_maps_engine import get_maps_engine


def google_maps_handler(parameters: Dict[str, Any], player=None, speak=None) -> str:
    """
    Executes Google Maps requests across geocoding, routing, places, elevation, and timezones.
    """
    engine = get_maps_engine()
    cmd = parameters.get("command", "").strip().lower()

    # Smart command inference if omitted
    if not cmd:
        if "origin" in parameters and ("destination" in parameters or "dest" in parameters):
            cmd = "directions"
        elif "address" in parameters:
            cmd = "geocode"
        elif "latlng" in parameters:
            cmd = "reverse-geocode"
        elif "query" in parameters:
            cmd = "places-search"
        elif "locations" in parameters:
            cmd = "elevation"
        else:
            cmd = "places-search"

    if cmd in ["directions", "route", "navigate"]:
        orig = parameters.get("origin") or parameters.get("from")
        dest = parameters.get("destination") or parameters.get("dest") or parameters.get("to")
        mode = parameters.get("mode", "DRIVE")
        if not orig or not dest:
            return "Please provide both an origin and destination for directions."

        res = engine.directions(origin=str(orig), destination=str(dest), mode=str(mode))
        if res.get("status") == "success":
            summary = res.get("summary", "")
            steps = res.get("steps", [])
            lines = [
                f"🗺️ **Route Directions: {orig} ➔ {dest}**",
                f"• **Distance & Time**: {summary}",
                f"• **Mode**: {mode.upper()}"
            ]
            if steps:
                lines.append("\n**Key Navigation Steps:**")
                for idx, s in enumerate(steps[:5], start=1):
                    lines.append(f"{idx}. {s}")
            content = "\n".join(lines)
            if player:
                player.write_log(f"🗺️ Route found: {orig} to {dest} ({summary})")
                player.show_content(f"Route: {orig} to {dest}", content)
            return f"The route from {orig} to {dest} is {summary}."
        elif res.get("status") == "config_error":
            return f"Google Maps directions is currently unavailable: {res.get('error')} {res.get('hint')}"
        else:
            return f"Could not find route between {orig} and {dest}: {res.get('error', 'Unknown error')}."

    elif cmd in ["geocode", "find_coordinates", "coordinates"]:
        addr = parameters.get("address") or parameters.get("query")
        if not addr:
            return "Please provide an address to geocode."
        res = engine.geocode(str(addr))
        if res.get("status") == "success":
            results = res.get("results", [])
            if not results:
                return f"No coordinates found for '{addr}'."
            top = results[0]
            lat, lng = top.get("lat"), top.get("lng")
            fmt = top.get("formatted_address")
            content = f"🗺️ **Geocoding Result**\n• Address: {fmt}\n• Latitude: {lat}\n• Longitude: {lng}"
            if player:
                player.write_log(f"🗺️ Coordinates: {fmt} -> {lat}, {lng}")
                player.show_content(f"Geocode: {addr}", content)
            return f"Coordinates for {addr} are {lat}, {lng} ({fmt})."
        elif res.get("status") == "config_error":
            return f"Geocoding unavailable: {res.get('error')} {res.get('hint')}"
        else:
            return f"Geocoding failed for {addr}: {res.get('error', 'Unknown error')}."

    elif cmd in ["reverse-geocode", "reverse_geocode"]:
        latlng = parameters.get("latlng") or parameters.get("coordinates")
        if not latlng:
            return "Please provide lat,lng coordinates for reverse geocoding."
        res = engine.reverse_geocode(str(latlng))
        if res.get("status") == "success":
            addr = res.get("primary_address", "Unknown address")
            content = f"🗺️ **Reverse Geocoding**\n• Coordinates: {latlng}\n• Address: {addr}"
            if player:
                player.write_log(f"🗺️ Reverse geocode: {latlng} -> {addr}")
                player.show_content(f"Reverse Geocode: {latlng}", content)
            return f"The location at coordinates {latlng} is {addr}."
        elif res.get("status") == "config_error":
            return f"Reverse geocoding unavailable: {res.get('error')}"
        else:
            return f"Reverse geocoding failed: {res.get('error', 'Unknown error')}."

    elif cmd in ["places-search", "places_search", "search", "search_places"]:
        q = parameters.get("query") or parameters.get("text")
        if not q:
            return "Please provide a search query for Google Places."
        loc = parameters.get("location")
        rad = parameters.get("radius")
        res = engine.places_search(str(q), location=loc, radius=float(rad) if rad else None)
        if res.get("status") == "success":
            places = res.get("places", [])
            if not places:
                return f"No places found matching '{q}'."
            lines = [f"🗺️ **Places found for '{q}':**"]
            for idx, p in enumerate(places[:5], start=1):
                rating_str = f" ⭐ {p.get('rating')}" if p.get("rating") else ""
                lines.append(f"{idx}. **{p.get('name')}**{rating_str} — {p.get('address')}")
            content = "\n".join(lines)
            if player:
                player.write_log(f"🗺️ Places search: {q} ({len(places)} found)")
                player.show_content(f"Places: {q}", content)
            top_name = places[0].get("name")
            return f"Found {len(places)} places for {q}. Top result is {top_name}."
        elif res.get("status") == "config_error":
            return f"Google Places search is not configured: {res.get('error')} {res.get('hint')}"
        else:
            return f"Places search failed: {res.get('error', 'Unknown error')}."

    elif cmd in ["elevation"]:
        locs = parameters.get("locations") or parameters.get("location")
        if not locs:
            return "Please provide lat,lng coordinates to query elevation."
        res = engine.elevation(str(locs))
        if res.get("status") == "success":
            elevs = res.get("elevations", [])
            if elevs:
                meters = elevs[0].get("elevation_m")
                return f"The elevation at {locs} is {meters} meters above sea level."
            return f"No elevation data returned for {locs}."
        elif res.get("status") == "config_error":
            return f"Elevation query unavailable: {res.get('error')}"
        else:
            return f"Elevation query failed: {res.get('error')}."

    elif cmd in ["timezone"]:
        loc = parameters.get("location") or parameters.get("latlng")
        if not loc:
            return "Please provide lat,lng coordinates to query timezone."
        res = engine.timezone(str(loc))
        if res.get("status") == "success":
            tz_name = res.get("timeZoneName")
            tz_id = res.get("timeZoneId")
            return f"The timezone at {loc} is {tz_name} ({tz_id})."
        elif res.get("status") == "config_error":
            return f"Timezone query unavailable: {res.get('error')}"
        else:
            return f"Timezone query failed: {res.get('error')}."

    return f"Unknown Google Maps command '{cmd}'. Available commands: directions, geocode, reverse-geocode, places-search, elevation, timezone."


TOOL = {
    "name": "google_maps",
    "description": "Google Maps Platform integration for directions/routes, geocoding, reverse geocoding, place searches, elevations, and timezones.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "command": {
                "type": "STRING",
                "enum": ["directions", "geocode", "reverse-geocode", "places-search", "places-nearby", "place-detail", "elevation", "timezone"],
                "description": "Map command to execute"
            },
            "origin": {
                "type": "STRING",
                "description": "Origin address or lat,lng for directions"
            },
            "destination": {
                "type": "STRING",
                "description": "Destination address or lat,lng for directions"
            },
            "address": {
                "type": "STRING",
                "description": "Physical address to geocode"
            },
            "query": {
                "type": "STRING",
                "description": "Search term for places search"
            },
            "latlng": {
                "type": "STRING",
                "description": "Latitude and longitude separated by comma (e.g. 37.422,-122.084)"
            },
            "mode": {
                "type": "STRING",
                "enum": ["DRIVE", "WALK", "BICYCLE", "TRANSIT"],
                "description": "Travel mode for directions"
            }
        }
    },
    "handler": google_maps_handler
}
