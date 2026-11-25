"""Geographic region selected by the user."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NamedTuple

from shapely.geometry.base import BaseGeometry

EARTH_RADIUS_KM = 6371.0088


class BBox(NamedTuple):
    """Bounding box in Overpass order: (south, west, north, east)."""

    south: float
    west: float
    north: float
    east: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.south + self.north) / 2.0, (self.west + self.east) / 2.0)

    def is_valid(self) -> bool:
        values = (self.south, self.west, self.north, self.east)
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            return False
        return (
            -90.0 <= self.south < self.north <= 90.0
            and -180.0 <= self.west < self.east <= 180.0
        )

    def area_km2(self) -> float:
        """Approximate spherical area of the box in square kilometres."""
        lat1, lat2 = math.radians(self.south), math.radians(self.north)
        dlon = math.radians(self.east - self.west)
        return abs(EARTH_RADIUS_KM**2 * dlon * (math.sin(lat2) - math.sin(lat1)))

    def contains(self, lat: float, lon: float) -> bool:
        return self.south <= lat <= self.north and self.west <= lon <= self.east


@dataclass
class Region:
    display_name: str
    latitude: float
    longitude: float
    bbox: BBox
    boundary: BaseGeometry | None = None
    osm_type: str | None = None
    osm_id: int | None = None
    place_class: str | None = None
    place_type: str | None = None
    importance: float | None = None

    @property
    def has_boundary(self) -> bool:
        return self.boundary is not None and not self.boundary.is_empty

    @property
    def key(self) -> str:
        if self.osm_type and self.osm_id is not None:
            return f"{self.osm_type}/{self.osm_id}"
        return f"bbox/{self.bbox.south:.5f},{self.bbox.west:.5f},{self.bbox.north:.5f},{self.bbox.east:.5f}"

    @property
    def label(self) -> str:
        kind = " / ".join(p for p in (self.place_class, self.place_type) if p)
        boundary = "boundary" if self.has_boundary else "no boundary"
        return f"{self.display_name}  [{kind or 'place'}; {boundary}]"
