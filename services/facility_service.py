"""Facility retrieval pipeline: query -> normalize -> validate -> filter -> flag.

The pipeline is UI-independent so later stages (routing, LLM agent) can
reuse it directly.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import config
from models.facility import Facility
from models.region import Region
from processing.normalize_facilities import normalize_elements
from processing.region_filter import filter_by_bbox, filter_by_boundary
from processing.validate_facilities import (
    deduplicate_by_source_id,
    flag_possible_duplicates,
    validate_coordinates,
)
from services.overpass_client import OverpassClient, build_overpass_query, check_query_area


@dataclass
class ProcessingReport:
    total_elements: int = 0
    unclassified: int = 0
    unsupported: int = 0
    missing_coordinates: int = 0
    invalid_coordinates: int = 0
    duplicates_removed: int = 0
    outside_region: int = 0
    unnamed: int = 0
    possible_duplicates: int = 0
    final_count: int = 0


@dataclass
class FacilityResult:
    region: Region
    category_keys: list[str]
    facilities: list[Facility]
    retrieved_at: str
    boundary_mode: str  # "boundary" or "bbox"
    report: ProcessingReport
    source_endpoint: str
    query: str
    warnings: list[str] = field(default_factory=list)

    def category_counts(self) -> dict[str, int]:
        """Counts for every requested category, including zeros."""
        counts = Counter(f.category for f in self.facilities)
        return {key: counts.get(key, 0) for key in self.category_keys}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def process_elements(
    elements: Sequence[dict[str, Any]],
    *,
    region: Region,
    category_keys: Sequence[str],
    retrieved_at: str,
) -> tuple[list[Facility], ProcessingReport, str]:
    """Turn raw Overpass elements into the final facility list.

    Returns (facilities, report, boundary_mode).
    """
    report = ProcessingReport(total_elements=len(elements))

    facilities, norm = normalize_elements(elements, retrieved_at, allowed_categories=set(category_keys))
    report.unclassified = norm.count("unclassified")
    report.unsupported = norm.count("unsupported_element")
    report.missing_coordinates = norm.count("missing_coordinates")

    facilities, invalid = validate_coordinates(facilities)
    report.invalid_coordinates = len(invalid)

    facilities, report.duplicates_removed = deduplicate_by_source_id(facilities)

    if region.has_boundary:
        facilities, report.outside_region = filter_by_boundary(facilities, region.boundary)
        boundary_mode = "boundary"
    else:
        # Ways/relations that intersect the box can have centres outside it.
        facilities, report.outside_region = filter_by_bbox(facilities, region.bbox)
        boundary_mode = "bbox"

    report.possible_duplicates = flag_possible_duplicates(facilities)
    report.unnamed = sum(1 for f in facilities if not f.has_name)

    order = {key: i for i, key in enumerate(config.CATEGORIES)}
    facilities.sort(key=lambda f: (order.get(f.category, 99), (f.name or "￿").casefold(), f.source_id))
    report.final_count = len(facilities)
    return facilities, report, boundary_mode


def build_warnings(result: FacilityResult) -> list[str]:
    warnings: list[str] = []
    r = result.report
    if result.boundary_mode == "bbox":
        warnings.append(
            "No administrative boundary was available for this region. Results are limited to its "
            "bounding box and may include places outside the actual region."
        )
    if r.final_count == 0:
        warnings.append(
            "No facilities of the selected categories were found. This means none are mapped in "
            "OpenStreetMap for this area; it does not mean none exist."
        )
    if r.unnamed:
        warnings.append(f"{r.unnamed} facilities have no name in OSM (flagged `missing_name`, not removed).")
    if r.possible_duplicates:
        warnings.append(
            f"{r.possible_duplicates} records share a name and category with a nearby record and may represent "
            "the same real-world facility (flagged `possible_duplicate`, not removed)."
        )
    if r.missing_coordinates or r.invalid_coordinates:
        warnings.append(
            f"{r.missing_coordinates + r.invalid_coordinates} records were excluded because their "
            "coordinates were missing or invalid."
        )
    if "shelter" in result.category_keys and any(f.category == "shelter" for f in result.facilities):
        warnings.append(
            "OSM `amenity=shelter` includes bus-stop, picnic and weather shelters, not only emergency shelters. "
            "Check the `shelter_type` tag; clearly non-emergency types are flagged `likely_not_emergency_shelter`."
        )
    return warnings


def build_result(
    region: Region,
    category_keys: Sequence[str],
    elements: Sequence[dict[str, Any]],
    *,
    retrieved_at: str,
    source_endpoint: str,
    query: str,
) -> FacilityResult:
    facilities, report, boundary_mode = process_elements(
        elements, region=region, category_keys=category_keys, retrieved_at=retrieved_at
    )
    result = FacilityResult(
        region=region,
        category_keys=list(category_keys),
        facilities=facilities,
        retrieved_at=retrieved_at,
        boundary_mode=boundary_mode,
        report=report,
        source_endpoint=source_endpoint,
        query=query,
    )
    result.warnings = build_warnings(result)
    return result


class FacilityService:
    """Convenience wrapper that runs the whole pipeline with a live Overpass client."""

    def __init__(self, overpass: OverpassClient | None = None):
        self.overpass = overpass or OverpassClient()

    def load(self, region: Region, category_keys: Sequence[str]) -> FacilityResult:
        check_query_area(region.bbox)
        query = build_overpass_query(region.bbox, category_keys)
        retrieved_at = utc_now_iso()
        elements, endpoint = self.overpass.fetch_with_endpoint(query)
        return build_result(
            region,
            category_keys,
            elements,
            retrieved_at=retrieved_at,
            source_endpoint=endpoint,
            query=query,
        )
