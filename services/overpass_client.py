"""Overpass API client and dynamic Overpass QL query construction."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

import requests

import config
from models.region import BBox
from services.http_client import (
    AllEndpointsFailedError,
    QueryTooLargeError,
    ServiceError,
    ServiceTimeoutError,
    UnexpectedResponseError,
    create_session,
    is_endpoint_down,
    request_json,
)

SERVICE_NAME = "Overpass API"


def tags_for_categories(category_keys: Iterable[str]) -> dict[str, list[str]]:
    """Group the OSM tags of the given categories by tag key, preserving order."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for key in category_keys:
        definition = config.CATEGORIES.get(key)
        if definition is None:
            raise ValueError(f"Unknown facility category: {key!r}")
        for tag_key, tag_value in definition.osm_tags:
            if tag_value not in grouped[tag_key]:
                grouped[tag_key].append(tag_value)
    return dict(grouped)


def _tag_filter(tag_key: str, values: list[str]) -> str:
    if len(values) == 1:
        return f'["{tag_key}"="{values[0]}"]'
    alternatives = "|".join(re.escape(v) for v in values)
    return f'["{tag_key}"~"^({alternatives})$"]'


def check_query_area(bbox: BBox, max_area_km2: float = config.MAX_QUERY_AREA_KM2) -> float:
    """Validate the bounding box and return its area; raise if it is unusable or too large."""
    if not bbox.is_valid():
        raise QueryTooLargeError(
            "The region's bounding box is invalid (or crosses the antimeridian), so it cannot be queried.",
            service=SERVICE_NAME,
        )
    area = bbox.area_km2()
    if area > max_area_km2:
        raise QueryTooLargeError(
            f"The region's bounding box covers about {area:,.0f} km², above the limit of "
            f"{max_area_km2:,.0f} km² for a single query on the public Overpass service. "
            "Please choose a smaller region (e.g. a city or district instead of a country or province).",
            service=SERVICE_NAME,
        )
    return area


def build_overpass_query(
    bbox: BBox,
    category_keys: Iterable[str],
    timeout_s: int = config.OVERPASS_QUERY_TIMEOUT_S,
) -> str:
    """Build an Overpass QL query for nodes, ways and relations in ``bbox``."""
    category_keys = list(category_keys)
    if not category_keys:
        raise ValueError("Select at least one facility category.")
    if not bbox.is_valid():
        raise ValueError("Invalid bounding box.")

    bbox_str = f"{bbox.south:.7f},{bbox.west:.7f},{bbox.north:.7f},{bbox.east:.7f}"
    statements = [
        f"  nwr{_tag_filter(tag_key, values)}({bbox_str});"
        for tag_key, values in tags_for_categories(category_keys).items()
    ]
    return "\n".join(
        [
            f"[out:json][timeout:{int(timeout_s)}];",
            "(",
            *statements,
            ");",
            "out center tags;",
        ]
    )


def _check_remark(payload: dict[str, Any]) -> None:
    """Overpass reports server-side failures with HTTP 200 plus a 'remark' field."""
    remark = str(payload.get("remark") or "")
    lowered = remark.lower()
    if not remark:
        return
    if "timed out" in lowered or "timeout" in lowered:
        raise ServiceTimeoutError(
            "The query timed out on the Overpass server, so the result would be incomplete. "
            "Try again later or choose a smaller region / fewer categories.",
            service=SERVICE_NAME,
        )
    if "out of memory" in lowered or "memory" in lowered:
        raise QueryTooLargeError(
            "The Overpass server ran out of memory for this query. Choose a smaller region or fewer categories.",
            service=SERVICE_NAME,
        )
    if "error" in lowered:
        raise ServiceError(f"The Overpass server reported an error: {remark}", service=SERVICE_NAME)


class OverpassClient:
    """Overpass client that falls back to the next endpoint when one is down.

    ``endpoints`` is a single URL or an ordered list of URLs. The next endpoint
    is tried only after a connection error, a client timeout or HTTP
    502/503/504; any other failure (a bad query, rate limiting, a server-side
    "out of memory" remark) is raised at once. Each endpoint gets at most
    ``1 + max_retries`` requests, so the total is bounded.
    """

    def __init__(
        self,
        endpoints: str | Sequence[str] = config.OVERPASS_URLS,
        *,
        user_agent: str = config.USER_AGENT,
        timeout: float = config.OVERPASS_HTTP_TIMEOUT_S,
        max_retries: int = config.HTTP_MAX_RETRIES,
        session: requests.Session | None = None,
    ):
        self.urls: tuple[str, ...] = (endpoints,) if isinstance(endpoints, str) else tuple(endpoints)
        if not self.urls:
            raise ValueError("At least one Overpass endpoint is required.")
        self.url = self.urls[0]  # primary endpoint
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or create_session(user_agent)

    def fetch(self, query: str) -> list[dict[str, Any]]:
        """Run ``query`` and return its ``elements``. Raises ServiceError on failure."""
        return self.fetch_with_endpoint(query)[0]

    def fetch_with_endpoint(self, query: str) -> tuple[list[dict[str, Any]], str]:
        """Run ``query`` and return ``(elements, url of the endpoint that answered)``."""
        failures: list[tuple[str, ServiceError]] = []
        for url in self.urls:
            try:
                payload = request_json(
                    self.session,
                    "POST",
                    url,
                    service=SERVICE_NAME,
                    timeout=self.timeout,
                    data={"data": query},
                    max_retries=self.max_retries,
                )
            except ServiceError as exc:
                if not is_endpoint_down(exc):
                    raise
                failures.append((url, exc))
                continue
            return _elements(payload), url
        if len(failures) == 1:
            raise failures[0][1]
        raise AllEndpointsFailedError(SERVICE_NAME, failures)


def _elements(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise UnexpectedResponseError("Unexpected response format (not a JSON object).", service=SERVICE_NAME)
    _check_remark(payload)
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise UnexpectedResponseError("Response does not contain an 'elements' list.", service=SERVICE_NAME)
    return elements
