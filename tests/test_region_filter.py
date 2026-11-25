import math

from models.facility import Facility
from models.region import BBox
from processing.region_filter import filter_by_bbox, filter_by_boundary, geometry_from_geojson
from processing.validate_facilities import is_valid_coordinate, validate_coordinates
from services.facility_service import build_result
from services.region_search import parse_nominatim_result


def fac(osm_id, lat, lon, category="hospital"):
    return Facility("node", osm_id, f"F{osm_id}", category, "Hospitals", lat, lon)


def test_boundary_filter_excludes_outside(square_region):
    inside = fac(1, 52.5, 13.5)
    on_edge = fac(2, 52.0, 13.5)
    outside_but_in_bbox = fac(3, 51.7, 12.7)
    kept, removed = filter_by_boundary([inside, on_edge, outside_but_in_bbox], square_region.boundary)
    assert [f.osm_id for f in kept] == [1, 2]
    assert removed == 1


def test_lat_lon_axis_order(square_region):
    # lat=13.5, lon=52.5 is the swapped position and must be outside.
    kept, _ = filter_by_boundary([fac(1, 13.5, 52.5)], square_region.boundary)
    assert kept == []


def test_bbox_filter():
    bbox = BBox(52.0, 13.0, 53.0, 14.0)
    kept, removed = filter_by_bbox([fac(1, 52.5, 13.5), fac(2, 54.0, 13.5)], bbox)
    assert [f.osm_id for f in kept] == [1]
    assert removed == 1


def test_geometry_from_geojson_variants():
    polygon = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    assert geometry_from_geojson(polygon) is not None
    assert geometry_from_geojson({"type": "Point", "coordinates": [1, 2]}) is None
    assert geometry_from_geojson(None) is None
    assert geometry_from_geojson({"type": "Polygon", "coordinates": "garbage"}) is None
    # Self-intersecting "bow tie" is repaired rather than rejected.
    bowtie = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}
    repaired = geometry_from_geojson(bowtie)
    assert repaired is not None and repaired.is_valid and repaired.area > 0


def test_coordinate_validation():
    assert is_valid_coordinate(52.5, 13.4)
    assert not is_valid_coordinate(91.0, 13.4)
    assert not is_valid_coordinate(52.5, -181.0)
    assert not is_valid_coordinate(math.nan, 13.4)
    assert not is_valid_coordinate(math.inf, 13.4)
    assert not is_valid_coordinate(0.0, 0.0)
    valid, invalid = validate_coordinates([fac(1, 52.5, 13.4), fac(2, 100.0, 13.4)])
    assert [f.osm_id for f in valid] == [1]
    assert [f.osm_id for f in invalid] == [2]


def test_pipeline_with_boundary(square_region, element_factory):
    elements = [
        element_factory("node", 1, lat=52.5, lon=13.5),
        element_factory("way", 2, lat=52.6, lon=13.6),
        element_factory("relation", 3, lat=52.7, lon=13.7),
        element_factory("node", 4, lat=51.7, lon=12.7),  # in bbox, outside boundary
        element_factory("node", 5, lat=95.0, lon=13.5),  # invalid
        element_factory("node", 1, lat=52.5, lon=13.5),  # repeated element
    ]
    result = build_result(
        square_region, ["hospital"], elements, retrieved_at="t", source_endpoint="test", query="q"
    )
    assert result.boundary_mode == "boundary"
    assert sorted(f.source_id for f in result.facilities) == ["node/1", "relation/3", "way/2"]
    assert result.report.outside_region == 1
    assert result.report.invalid_coordinates == 1
    assert result.report.duplicates_removed == 1
    assert result.category_counts() == {"hospital": 3}


def test_pipeline_without_boundary_warns(bbox_only_region, element_factory):
    elements = [element_factory("node", 1, lat=52.5, lon=13.5), element_factory("way", 2, lat=55.0, lon=13.5)]
    result = build_result(
        bbox_only_region, ["hospital", "police"], elements, retrieved_at="t", source_endpoint="test", query="q"
    )
    assert result.boundary_mode == "bbox"
    assert [f.osm_id for f in result.facilities] == [1]
    assert result.category_counts() == {"hospital": 1, "police": 0}
    assert any("bounding box" in w for w in result.warnings)


def test_empty_result_warning(square_region):
    result = build_result(square_region, ["hospital"], [], retrieved_at="t", source_endpoint="test", query="q")
    assert result.facilities == []
    assert any("does not mean none exist" in w for w in result.warnings)


def test_parse_nominatim_result():
    item = {
        "osm_type": "relation",
        "osm_id": "62422",
        "lat": "52.5170365",
        "lon": "13.3888599",
        "display_name": "Berlin, Germany",
        "category": "boundary",
        "type": "administrative",
        "boundingbox": ["52.3382448", "52.6755087", "13.0883450", "13.7611609"],
        "geojson": {"type": "Polygon", "coordinates": [[[13.1, 52.4], [13.7, 52.4], [13.7, 52.6], [13.1, 52.4]]]},
    }
    region = parse_nominatim_result(item)
    assert region.key == "relation/62422"
    assert region.bbox == BBox(52.3382448, 13.0883450, 52.6755087, 13.7611609)
    assert region.has_boundary

    item_point = dict(item, geojson={"type": "Point", "coordinates": [13.38, 52.51]})
    assert not parse_nominatim_result(item_point).has_boundary
    assert parse_nominatim_result({"lat": "x"}) is None
