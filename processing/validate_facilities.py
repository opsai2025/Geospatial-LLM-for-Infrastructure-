"""Coordinate validation, ID-based deduplication and possible-duplicate flagging."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

import config
from models.facility import Facility
from models.region import EARTH_RADIUS_KM


def is_valid_coordinate(lat: float, lon: float) -> bool:
    """True for finite WGS84 coordinates in range, excluding the (0, 0) placeholder."""
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return False
    if isinstance(lat, bool) or isinstance(lon, bool):
        return False
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    return not (lat == 0.0 and lon == 0.0)


def validate_coordinates(facilities: Iterable[Facility]) -> tuple[list[Facility], list[Facility]]:
    """Split facilities into (valid, invalid) by their coordinates."""
    valid: list[Facility] = []
    invalid: list[Facility] = []
    for facility in facilities:
        (valid if is_valid_coordinate(facility.latitude, facility.longitude) else invalid).append(facility)
    return valid, invalid


def deduplicate_by_source_id(facilities: Iterable[Facility]) -> tuple[list[Facility], int]:
    """Remove repeated records of the same OSM element (same type and ID).

    This only removes repeats of one OSM element. A real facility mapped as
    several elements (e.g. a node and a building way) is *not* merged; see
    ``flag_possible_duplicates``.
    """
    seen: set[tuple[str, int]] = set()
    unique: list[Facility] = []
    removed = 0
    for facility in facilities:
        key = (facility.osm_type, facility.osm_id)
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        unique.append(facility)
    return unique, removed


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * 1000 * math.asin(min(1.0, math.sqrt(a)))


def _name_key(name: str) -> str:
    return " ".join(name.casefold().split())


def flag_possible_duplicates(
    facilities: list[Facility],
    max_distance_m: float = config.POSSIBLE_DUPLICATE_DISTANCE_M,
) -> int:
    """Flag same-category, same-name records within ``max_distance_m`` of each other.

    Records are only flagged (``possible_duplicate:<type>/<id>``), never
    removed, because nearby same-named elements can be distinct facilities.
    Unnamed duplicates cannot be detected this way. Returns the number of
    records that received a flag.
    """
    groups: dict[tuple[str, str], list[Facility]] = defaultdict(list)
    for facility in facilities:
        if facility.name:
            groups[(facility.category, _name_key(facility.name))].append(facility)

    flagged: set[str] = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        for i, first in enumerate(members):
            for second in members[i + 1 :]:
                distance = haversine_m(first.latitude, first.longitude, second.latitude, second.longitude)
                if distance <= max_distance_m:
                    first.add_flag(f"possible_duplicate:{second.source_id}")
                    second.add_flag(f"possible_duplicate:{first.source_id}")
                    flagged.update((first.source_id, second.source_id))
    return len(flagged)
