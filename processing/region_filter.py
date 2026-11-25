"""Boundary parsing and spatial filtering of facilities."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.validation import make_valid

from models.facility import Facility
from models.region import BBox

POLYGON_TYPES = (Polygon, MultiPolygon)


def _polygonal_part(geometry: BaseGeometry) -> BaseGeometry | None:
    if isinstance(geometry, POLYGON_TYPES):
        return geometry
    if isinstance(geometry, GeometryCollection):
        parts = [g for g in geometry.geoms if isinstance(g, POLYGON_TYPES) and not g.is_empty]
        if parts:
            return unary_union(parts)
    return None


def geometry_from_geojson(geojson: Any) -> BaseGeometry | None:
    """Return a valid (Multi)Polygon from a GeoJSON geometry, or None.

    Point and line geometries (e.g. a city mapped only as a node) are not
    boundaries and return None, so callers fall back to the bounding box.
    """
    if not isinstance(geojson, dict) or geojson.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    try:
        geometry = shape(geojson)
    except Exception:  # malformed coordinates of any kind
        return None
    if geometry.is_empty:
        return None
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    geometry = _polygonal_part(geometry)
    if geometry is None or geometry.is_empty or geometry.area == 0:
        return None
    return geometry


def filter_by_bbox(facilities: Iterable[Facility], bbox: BBox) -> tuple[list[Facility], int]:
    """Keep facilities whose coordinates lie in ``bbox``. Returns (kept, removed_count)."""
    kept: list[Facility] = []
    removed = 0
    for facility in facilities:
        if bbox.contains(facility.latitude, facility.longitude):
            kept.append(facility)
        else:
            removed += 1
    return kept, removed


def filter_by_boundary(facilities: Iterable[Facility], boundary: BaseGeometry) -> tuple[list[Facility], int]:
    """Keep facilities inside or on ``boundary``. Returns (kept, removed_count)."""
    prepared = prep(boundary)
    kept: list[Facility] = []
    removed = 0
    for facility in facilities:
        # Shapely uses (x, y) = (longitude, latitude).
        if prepared.covers(Point(facility.longitude, facility.latitude)):
            kept.append(facility)
        else:
            removed += 1
    return kept, removed
