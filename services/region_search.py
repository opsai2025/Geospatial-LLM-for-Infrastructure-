"""Region search and boundary retrieval through the Nominatim search API."""

from __future__ import annotations

import threading
import time
from typing import Any

import requests

import config
from models.region import BBox, Region
from processing.region_filter import geometry_from_geojson
from services.http_client import UnexpectedResponseError, create_session, request_json

SERVICE_NAME = "Nominatim"

_throttle_lock = threading.Lock()
_last_request_at = 0.0


def _throttle(min_interval: float) -> None:
    """Keep at least ``min_interval`` seconds between requests (process-wide)."""
    global _last_request_at
    with _throttle_lock:
        wait = _last_request_at + min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.monotonic()


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_nominatim_result(item: dict[str, Any]) -> Region | None:
    """Convert one Nominatim ``jsonv2`` result into a Region, or None if unusable."""
    if not isinstance(item, dict):
        return None

    lat, lon = _to_float(item.get("lat")), _to_float(item.get("lon"))
    raw_bbox = item.get("boundingbox")
    if lat is None or lon is None or not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return None

    # Nominatim order is [south, north, west, east].
    south, north, west, east = (_to_float(v) for v in raw_bbox)
    if None in (south, north, west, east):
        return None
    bbox = BBox(south=south, west=west, north=north, east=east)
    if not bbox.is_valid():
        return None

    osm_id = item.get("osm_id")
    try:
        osm_id = int(osm_id) if osm_id is not None else None
    except (TypeError, ValueError):
        osm_id = None

    importance = _to_float(item.get("importance"))

    return Region(
        display_name=str(item.get("display_name") or item.get("name") or "Unnamed region"),
        latitude=lat,
        longitude=lon,
        bbox=bbox,
        boundary=geometry_from_geojson(item.get("geojson")),
        osm_type=item.get("osm_type"),
        osm_id=osm_id,
        place_class=item.get("category") or item.get("class"),
        place_type=item.get("type"),
        importance=importance,
    )


class NominatimClient:
    def __init__(
        self,
        base_url: str = config.NOMINATIM_URL,
        *,
        user_agent: str = config.USER_AGENT,
        contact_email: str = config.CONTACT,
        timeout: float = config.NOMINATIM_TIMEOUT_S,
        language: str = config.NOMINATIM_LANGUAGE,
        min_interval: float = config.NOMINATIM_MIN_INTERVAL_S,
        polygon_threshold: float = config.NOMINATIM_POLYGON_THRESHOLD,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url
        self.contact_email = contact_email if "@" in (contact_email or "") else ""
        self.timeout = timeout
        self.language = language
        self.min_interval = min_interval
        self.polygon_threshold = polygon_threshold
        self.session = session or create_session(user_agent)

    def search(self, query: str, limit: int = config.NOMINATIM_RESULT_LIMIT) -> list[Region]:
        """Return matching regions, most relevant first. Raises ServiceError on failure."""
        query = (query or "").strip()
        if not query:
            raise ValueError("Please enter a city, municipality or region name.")

        params: dict[str, Any] = {
            "q": query,
            "format": "jsonv2",
            "polygon_geojson": 1,
            "polygon_threshold": self.polygon_threshold,
            "limit": max(1, min(int(limit), 40)),
            "accept-language": self.language,
        }
        if self.contact_email:
            params["email"] = self.contact_email

        _throttle(self.min_interval)
        payload = request_json(
            self.session, "GET", self.base_url, service=SERVICE_NAME, timeout=self.timeout, params=params
        )
        if not isinstance(payload, list):
            raise UnexpectedResponseError("Unexpected search response format.", service=SERVICE_NAME)

        regions: list[Region] = []
        seen: set[str] = set()
        for item in payload:
            region = parse_nominatim_result(item)
            if region is None or region.key in seen:
                continue
            seen.add(region.key)
            regions.append(region)
        return regions
