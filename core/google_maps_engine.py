"""
JARVIS H3.2 — Google Maps Engine
Native Python implementation of the Google Maps Platform API suite.
Implements the 8 core operations from deusyu/google-maps-skill:
  - geocode
  - reverse-geocode
  - directions (Routes v2)
  - places-search (Places v1)
  - places-nearby (Places v1)
  - place-detail (Places v1)
  - elevation
  - timezone

Features:
  - Zero external npm/bun dependencies (pure Python with requests/urllib).
  - Clean API key resolution from config/api_keys.json or env.
  - Transparent error diagnostics (no fabricated data when unconfigured).
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import requests

logger = logging.getLogger("jarvis.maps")

CONFIG_PATH = Path("config/api_keys.json")


class GoogleMapsEngine:
    """REST client for Google Maps Platform APIs."""

    def __init__(self, api_key: Optional[str] = None):
        self._explicit_key = api_key

    def get_api_key(self) -> Optional[str]:
        """Resolves API key from constructor, config file, or environment."""
        if self._explicit_key:
            return self._explicit_key

        env_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if env_key and env_key.strip():
            return env_key.strip()

        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    for k in ["google_maps_api_key", "google_maps", "gmaps_api_key", "GMAPS_API_KEY"]:
                        val = cfg.get(k)
                        if val and isinstance(val, str) and val.strip():
                            return val.strip()
            except Exception as e:
                logger.debug(f"Failed to read {CONFIG_PATH}: {e}")

        return None

    def _require_api_key(self) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        key = self.get_api_key()
        if not key:
            return None, {
                "status": "config_error",
                "error": "GOOGLE_MAPS_API_KEY is not configured.",
                "hint": "Please add 'google_maps_api_key' to config/api_keys.json or export GOOGLE_MAPS_API_KEY in your environment."
            }
        return key, None

    def geocode(self, address: str) -> Dict[str, Any]:
        """Converts an address into geographic coordinates."""
        key, err = self._require_api_key()
        if err:
            return err

        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": address, "key": key}
        try:
            r = requests.get(url, params=params, timeout=8)
            data = r.json()
            if data.get("status") != "OK":
                return {
                    "status": "api_error",
                    "error": data.get("error_message") or data.get("status"),
                    "raw": data
                }
            results = data.get("results", [])
            formatted = []
            for item in results:
                loc = item.get("geometry", {}).get("location", {})
                formatted.append({
                    "formatted_address": item.get("formatted_address"),
                    "lat": loc.get("lat"),
                    "lng": loc.get("lng"),
                    "place_id": item.get("place_id"),
                    "location_type": item.get("geometry", {}).get("location_type")
                })
            return {"status": "success", "results": formatted, "count": len(formatted)}
        except Exception as e:
            return {"status": "network_error", "error": str(e)}

    def reverse_geocode(self, latlng: str) -> Dict[str, Any]:
        """Converts coordinates (lat,lng) into a human-readable address."""
        key, err = self._require_api_key()
        if err:
            return err

        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"latlng": latlng, "key": key}
        try:
            r = requests.get(url, params=params, timeout=8)
            data = r.json()
            if data.get("status") != "OK":
                return {
                    "status": "api_error",
                    "error": data.get("error_message") or data.get("status"),
                    "raw": data
                }
            results = data.get("results", [])
            addresses = [x.get("formatted_address") for x in results if x.get("formatted_address")]
            return {
                "status": "success",
                "latlng": latlng,
                "primary_address": addresses[0] if addresses else None,
                "all_addresses": addresses
            }
        except Exception as e:
            return {"status": "network_error", "error": str(e)}

    def directions(
        self,
        origin: str,
        destination: str,
        mode: str = "DRIVE"
    ) -> Dict[str, Any]:
        """
        Computes routes between origin and destination via Google Routes API v2.
        Mode: DRIVE, WALK, BICYCLE, TRANSIT
        """
        key, err = self._require_api_key()
        if err:
            return err

        mode_upper = mode.upper()
        if mode_upper not in ["DRIVE", "WALK", "BICYCLE", "TRANSIT"]:
            mode_upper = "DRIVE"

        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.description,routes.legs"
        }
        body = {
            "origin": {"address": origin},
            "destination": {"address": destination},
            "travelMode": mode_upper
        }
        try:
            r = requests.post(url, headers=headers, json=body, timeout=10)
            data = r.json()
            routes = data.get("routes", [])
            if not routes:
                return {
                    "status": "no_routes",
                    "error": data.get("error", {}).get("message") or "No route found between points.",
                    "raw": data
                }
            best_route = routes[0]
            distance_meters = best_route.get("distanceMeters", 0)
            duration_str = best_route.get("duration", "0s")
            # Parse duration seconds
            duration_sec = 0
            if duration_str.endswith("s"):
                try:
                    duration_sec = float(duration_str[:-1])
                except ValueError:
                    pass

            distance_km = round(distance_meters / 1000.0, 2)
            duration_min = round(duration_sec / 60.0, 1)

            steps = []
            legs = best_route.get("legs", [])
            if legs:
                for step in legs[0].get("steps", []):
                    instr = step.get("navigationInstruction", {}).get("instructions")
                    if instr:
                        steps.append(instr)

            return {
                "status": "success",
                "origin": origin,
                "destination": destination,
                "mode": mode_upper,
                "distance_km": distance_km,
                "duration_min": duration_min,
                "summary": f"{distance_km} km, approximately {duration_min} mins via {mode_upper.lower()}",
                "steps": steps[:8]
            }
        except Exception as e:
            return {"status": "network_error", "error": str(e)}

    def places_search(
        self,
        query: str,
        location: Optional[str] = None,
        radius: Optional[float] = None
    ) -> Dict[str, Any]:
        """Searches places using Places API v1 searchText."""
        key, err = self._require_api_key()
        if err:
            return err

        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount"
        }
        body: Dict[str, Any] = {"textQuery": query}
        if location and radius:
            try:
                lat, lng = [float(x.strip()) for x in location.split(",")]
                body["locationBias"] = {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": float(radius)
                    }
                }
            except Exception:
                pass

        try:
            r = requests.post(url, headers=headers, json=body, timeout=8)
            data = r.json()
            places = data.get("places", [])
            formatted = []
            for p in places:
                name = p.get("displayName", {}).get("text", "Unknown")
                formatted.append({
                    "name": name,
                    "address": p.get("formattedAddress"),
                    "rating": p.get("rating"),
                    "reviews": p.get("userRatingCount"),
                    "place_id": p.get("id"),
                    "location": p.get("location")
                })
            return {"status": "success", "query": query, "places": formatted, "count": len(formatted)}
        except Exception as e:
            return {"status": "network_error", "error": str(e)}

    def places_nearby(
        self,
        location: str,
        radius: float = 1000.0,
        place_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Finds nearby places within radius (meters) using Places API v1 searchNearby."""
        key, err = self._require_api_key()
        if err:
            return err

        try:
            lat, lng = [float(x.strip()) for x in location.split(",")]
        except Exception:
            return {"status": "input_error", "error": "Location must be formatted as 'lat,lng'"}

        url = "https://places.googleapis.com/v1/places:searchNearby"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.location"
        }
        body: Dict[str, Any] = {
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius)
                }
            }
        }
        if place_type:
            body["includedTypes"] = [place_type]

        try:
            r = requests.post(url, headers=headers, json=body, timeout=8)
            data = r.json()
            places = data.get("places", [])
            formatted = []
            for p in places:
                formatted.append({
                    "name": p.get("displayName", {}).get("text", "Unknown"),
                    "address": p.get("formattedAddress"),
                    "rating": p.get("rating"),
                    "place_id": p.get("id"),
                    "location": p.get("location")
                })
            return {"status": "success", "places": formatted, "count": len(formatted)}
        except Exception as e:
            return {"status": "network_error", "error": str(e)}

    def place_detail(self, place_id: str) -> Dict[str, Any]:
        """Gets detailed info for a place."""
        key, err = self._require_api_key()
        if err:
            return err

        url = f"https://places.googleapis.com/v1/places/{place_id}"
        headers = {
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "id,displayName,formattedAddress,location,rating,currentOpeningHours,websiteUri,internationalPhoneNumber"
        }
        try:
            r = requests.get(url, headers=headers, timeout=8)
            p = r.json()
            if "error" in p:
                return {"status": "api_error", "error": p["error"].get("message")}
            return {
                "status": "success",
                "name": p.get("displayName", {}).get("text"),
                "address": p.get("formattedAddress"),
                "rating": p.get("rating"),
                "phone": p.get("internationalPhoneNumber"),
                "website": p.get("websiteUri"),
                "open_now": p.get("currentOpeningHours", {}).get("openNow"),
                "weekday_descriptions": p.get("currentOpeningHours", {}).get("weekdayDescriptions", [])
            }
        except Exception as e:
            return {"status": "network_error", "error": str(e)}

    def elevation(self, locations: str) -> Dict[str, Any]:
        """Queries elevation for one or more lat,lng coordinates."""
        key, err = self._require_api_key()
        if err:
            return err

        url = "https://maps.googleapis.com/maps/api/elevation/json"
        params = {"locations": locations, "key": key}
        try:
            r = requests.get(url, params=params, timeout=8)
            data = r.json()
            if data.get("status") != "OK":
                return {"status": "api_error", "error": data.get("error_message") or data.get("status")}
            results = data.get("results", [])
            return {
                "status": "success",
                "elevations": [
                    {"elevation_m": round(x.get("elevation", 0), 2), "location": x.get("location")}
                    for x in results
                ]
            }
        except Exception as e:
            return {"status": "network_error", "error": str(e)}

    def timezone(self, location: str, timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Gets timezone information for a given coordinate."""
        key, err = self._require_api_key()
        if err:
            return err

        ts = timestamp or int(time.time())
        url = "https://maps.googleapis.com/maps/api/timezone/json"
        params = {"location": location, "timestamp": ts, "key": key}
        try:
            r = requests.get(url, params=params, timeout=8)
            data = r.json()
            if data.get("status") != "OK":
                return {"status": "api_error", "error": data.get("error_message") or data.get("status")}
            return {
                "status": "success",
                "timeZoneId": data.get("timeZoneId"),
                "timeZoneName": data.get("timeZoneName"),
                "rawOffset": data.get("rawOffset"),
                "dstOffset": data.get("dstOffset")
            }
        except Exception as e:
            return {"status": "network_error", "error": str(e)}


# Singleton instance
_maps_engine_instance: Optional[GoogleMapsEngine] = None

def get_maps_engine() -> GoogleMapsEngine:
    global _maps_engine_instance
    if _maps_engine_instance is None:
        _maps_engine_instance = GoogleMapsEngine()
    return _maps_engine_instance
