"""Convert raw Overpass elements into normalized Facility records."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from typing import Any

import config
from models.facility import OSM_ELEMENT_TYPES, Facility

# (tag key, tag value) -> category key
TAG_INDEX: dict[tuple[str, str], str] = {
    tag: definition.key for definition in config.CATEGORIES.values() for tag in definition.osm_tags
}

LOCATION_PRECISION = {
    "node": "osm_node",
    "way": "osm_way_center",
    "relation": "osm_relation_center",
}


def classify_tags(tags: dict[str, str], allowed: Collection[str] | None = None) -> str | None:
    """Return the category key for ``tags``, or None if no supported tag matches.

    Tag keys are checked in ``config.TAG_KEY_PRIORITY`` order so the result is
    deterministic when an element has several supported tags. With ``allowed``,
    only those categories are considered.
    """
    priority = list(config.TAG_KEY_PRIORITY) + sorted({k for k, _ in TAG_INDEX} - set(config.TAG_KEY_PRIORITY))
    for tag_key in priority:
        value = tags.get(tag_key)
        if value is None:
            continue
        # OSM permits multiple values separated by ';' (e.g. "clinic;pharmacy").
        for part in str(value).split(";"):
            category = TAG_INDEX.get((tag_key, part.strip()))
            if category and (allowed is None or category in allowed):
                return category
    return None


def _first(tags: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = tags.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def build_address(tags: dict[str, str]) -> str | None:
    """Compose an address from ``addr:*`` tags only. Returns None when absent."""
    full = _first(tags, "addr:full")
    if full:
        return full

    street = _first(tags, "addr:street", "addr:place")
    number = _first(tags, "addr:housenumber")
    line1 = " ".join(p for p in (street, number) if p) or None
    postcode = _first(tags, "addr:postcode")
    city = _first(tags, "addr:city", "addr:town", "addr:village", "addr:suburb")
    line2 = " ".join(p for p in (postcode, city) if p) or None

    parts = [p for p in (line1, line2) if p]
    return ", ".join(parts) if parts else None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_coordinates(element: dict[str, Any]) -> tuple[float, float, str] | None:
    """Return (lat, lon, precision) for an Overpass element, or None if absent.

    Nodes use their own position; ways and relations use the ``center``
    returned by ``out center``. Centres are approximate marker positions,
    not entrances or access points.
    """
    element_type = element.get("type")
    if element_type == "node":
        lat, lon = _to_float(element.get("lat")), _to_float(element.get("lon"))
    else:
        center = element.get("center")
        if not isinstance(center, dict):
            return None
        lat, lon = _to_float(center.get("lat")), _to_float(center.get("lon"))
    if lat is None or lon is None:
        return None
    return lat, lon, LOCATION_PRECISION.get(element_type, "unknown")


def _shelter_flags(tags: dict[str, str]) -> list[str]:
    shelter_type = _first(tags, "shelter_type")
    if shelter_type is None:
        return ["shelter_type_unspecified"]
    flags = [f"shelter_type:{shelter_type}"]
    if shelter_type in config.NON_EMERGENCY_SHELTER_TYPES:
        flags.append("likely_not_emergency_shelter")
    return flags


def normalize_element(
    element: dict[str, Any],
    retrieved_at: str,
    allowed_categories: Collection[str] | None = None,
) -> tuple[Facility | None, str | None]:
    """Normalize one element. Returns (facility, None) or (None, skip_reason)."""
    if not isinstance(element, dict):
        return None, "unsupported_element"
    element_type = element.get("type")
    try:
        osm_id = int(element.get("id"))
    except (TypeError, ValueError):
        return None, "unsupported_element"
    if element_type not in OSM_ELEMENT_TYPES:
        return None, "unsupported_element"

    tags = element.get("tags")
    if not isinstance(tags, dict):
        return None, "unclassified"
    tags = {str(k): str(v) for k, v in tags.items()}

    category = classify_tags(tags, allowed_categories)
    if category is None:
        return None, "unclassified"

    coords = extract_coordinates(element)
    if coords is None:
        return None, "missing_coordinates"
    lat, lon, precision = coords

    facility = Facility(
        osm_type=element_type,
        osm_id=osm_id,
        name=_first(tags, "name"),
        category=category,
        category_label=config.CATEGORIES[category].label,
        latitude=lat,
        longitude=lon,
        address=build_address(tags),
        operator=_first(tags, "operator"),
        phone=_first(tags, "phone", "contact:phone"),
        website=_first(tags, "website", "contact:website", "url"),
        raw_tags=tags,
        location_precision=precision,
        source=config.DATA_SOURCE,
        retrieved_at=retrieved_at,
    )
    if not facility.has_name:
        facility.add_flag("missing_name")
    if category == "shelter":
        for flag in _shelter_flags(tags):
            facility.add_flag(flag)
    return facility, None


@dataclass
class NormalizationReport:
    total_elements: int = 0
    normalized: int = 0
    skipped: dict[str, int] = field(default_factory=dict)

    def count(self, reason: str) -> int:
        return self.skipped.get(reason, 0)


def normalize_elements(
    elements: Iterable[dict[str, Any]],
    retrieved_at: str,
    allowed_categories: Collection[str] | None = None,
) -> tuple[list[Facility], NormalizationReport]:
    report = NormalizationReport()
    facilities: list[Facility] = []
    for element in elements:
        report.total_elements += 1
        facility, reason = normalize_element(element, retrieved_at, allowed_categories)
        if facility is None:
            report.skipped[reason] = report.skipped.get(reason, 0) + 1
        else:
            facilities.append(facility)
    report.normalized = len(facilities)
    return facilities, report
