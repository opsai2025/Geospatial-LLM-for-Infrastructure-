"""CSV, GeoJSON and JSON export of normalized facility records."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pandas as pd

import config
from models.facility import Facility

FLAT_COLUMNS = [
    "source_id",
    "osm_type",
    "osm_id",
    "name",
    "category",
    "category_label",
    "latitude",
    "longitude",
    "location_precision",
    "address",
    "operator",
    "phone",
    "website",
    "quality_flags",
    "source",
    "retrieved_at",
    "osm_url",
    "raw_tags_json",
]


def build_export_metadata(
    *,
    region_name: str | None = None,
    region_id: str | None = None,
    boundary_mode: str | None = None,
    category_keys: Sequence[str] | None = None,
    retrieved_at: str | None = None,
    source_endpoint: str | None = None,
) -> dict[str, Any]:
    return {
        "source": config.DATA_SOURCE,
        "attribution": config.DATA_ATTRIBUTION,
        "license": config.DATA_LICENSE,
        "license_url": config.DATA_LICENSE_URL,
        "source_endpoint": source_endpoint,
        "region": region_name,
        "region_osm_id": region_id,
        "spatial_filter": boundary_mode,
        "categories": list(category_keys or []),
        "retrieved_at": retrieved_at,
        "operational_status": "not verified",
        "disclaimer": config.STATUS_DISCLAIMER,
        "generator": f"{config.APP_NAME} {config.APP_VERSION}",
    }


def facilities_to_dataframe(facilities: Sequence[Facility]) -> pd.DataFrame:
    rows = []
    for f in facilities:
        rows.append(
            {
                "source_id": f.source_id,
                "osm_type": f.osm_type,
                "osm_id": f.osm_id,
                "name": f.name,
                "category": f.category,
                "category_label": f.category_label,
                "latitude": f.latitude,
                "longitude": f.longitude,
                "location_precision": f.location_precision,
                "address": f.address,
                "operator": f.operator,
                "phone": f.phone,
                "website": f.website,
                "quality_flags": ";".join(f.quality_flags),
                "source": f.source,
                "retrieved_at": f.retrieved_at,
                "osm_url": f.osm_url,
                "raw_tags_json": json.dumps(f.raw_tags, ensure_ascii=False, sort_keys=True),
            }
        )
    return pd.DataFrame(rows, columns=FLAT_COLUMNS)


def to_csv_bytes(facilities: Sequence[Facility]) -> bytes:
    # UTF-8 with BOM so spreadsheet tools display non-Latin names correctly.
    return facilities_to_dataframe(facilities).to_csv(index=False).encode("utf-8-sig")


def to_geojson(facilities: Sequence[Facility], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    features = []
    for f in facilities:
        properties = f.to_dict()
        properties.pop("latitude")
        properties.pop("longitude")
        features.append(
            {
                "type": "Feature",
                "id": f.source_id,
                "geometry": {"type": "Point", "coordinates": [f.longitude, f.latitude]},
                "properties": properties,
            }
        )
    collection: dict[str, Any] = {"type": "FeatureCollection", "features": features}
    if metadata:
        collection["metadata"] = metadata  # GeoJSON "foreign member" (RFC 7946 §6.1)
    return collection


def to_geojson_bytes(facilities: Sequence[Facility], metadata: dict[str, Any] | None = None) -> bytes:
    return json.dumps(to_geojson(facilities, metadata), ensure_ascii=False, indent=2).encode("utf-8")


def to_json(facilities: Sequence[Facility], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "metadata": metadata or build_export_metadata(),
        "count": len(facilities),
        "facilities": [f.to_dict() for f in facilities],
    }


def to_json_bytes(facilities: Sequence[Facility], metadata: dict[str, Any] | None = None) -> bytes:
    return json.dumps(to_json(facilities, metadata), ensure_ascii=False, indent=2).encode("utf-8")
