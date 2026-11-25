import pytest

import config
from processing.normalize_facilities import (
    build_address,
    classify_tags,
    extract_coordinates,
    normalize_element,
    normalize_elements,
)

TS = "2026-10-19T12:00:00+00:00"


@pytest.mark.parametrize(
    "tags, expected",
    [
        ({"amenity": "hospital"}, "hospital"),
        ({"amenity": "clinic"}, "clinic"),
        ({"amenity": "doctors"}, "clinic"),
        ({"amenity": "police"}, "police"),
        ({"amenity": "fire_station"}, "fire_station"),
        ({"office": "government"}, "government"),
        ({"amenity": "townhall"}, "townhall"),
        ({"amenity": "courthouse"}, "courthouse"),
        ({"amenity": "pharmacy"}, "pharmacy"),
        ({"amenity": "shelter"}, "shelter"),
        ({"amenity": "fuel"}, "fuel"),
        ({"amenity": "cafe"}, None),
        ({"shop": "bakery"}, None),
        ({}, None),
    ],
)
def test_classify_every_supported_tag(tags, expected):
    assert classify_tags(tags) == expected


def test_every_configured_tag_is_classified():
    for key, definition in config.CATEGORIES.items():
        for tag_key, tag_value in definition.osm_tags:
            assert classify_tags({tag_key: tag_value}) == key


def test_amenity_takes_priority_over_office():
    tags = {"amenity": "townhall", "office": "government"}
    assert classify_tags(tags) == "townhall"
    # ...unless only government offices were requested
    assert classify_tags(tags, allowed={"government"}) == "government"


def test_semicolon_separated_values():
    assert classify_tags({"amenity": "cafe;pharmacy"}) == "pharmacy"


def test_node_way_relation_coordinates(element_factory):
    assert extract_coordinates(element_factory("node", lat=1.5, lon=2.5)) == (1.5, 2.5, "osm_node")
    assert extract_coordinates(element_factory("way", lat=1.5, lon=2.5)) == (1.5, 2.5, "osm_way_center")
    assert extract_coordinates(element_factory("relation", lat=1.5, lon=2.5)) == (1.5, 2.5, "osm_relation_center")
    assert extract_coordinates(element_factory("way", center=False)) is None
    assert extract_coordinates({"type": "node", "id": 1, "lat": "x", "lon": 3}) is None


def test_normalize_preserves_tags_and_keeps_missing_as_null(element_factory):
    tags = {"amenity": "hospital", "emergency": "yes", "name": "Charité", "addr:street": "Luisenstraße"}
    facility, reason = normalize_element(element_factory("way", 99, tags), TS)
    assert reason is None
    assert facility.osm_type == "way" and facility.osm_id == 99
    assert facility.source_id == "way/99"
    assert facility.category == "hospital"
    assert facility.category_label == "Hospitals"
    assert facility.name == "Charité"
    assert facility.raw_tags == tags
    assert facility.address == "Luisenstraße"
    assert facility.operator is None
    assert facility.phone is None
    assert facility.website is None
    assert facility.location_precision == "osm_way_center"
    assert facility.source == "OpenStreetMap"
    assert facility.retrieved_at == TS
    assert facility.quality_flags == []


def test_unnamed_is_flagged_not_dropped(element_factory):
    facility, reason = normalize_element(element_factory(tags={"amenity": "police"}), TS)
    assert reason is None
    assert facility.name is None
    assert "missing_name" in facility.quality_flags


def test_contact_fallback_tags(element_factory):
    tags = {"amenity": "pharmacy", "contact:phone": "+49 30 1", "contact:website": "https://example.org"}
    facility, _ = normalize_element(element_factory(tags=tags), TS)
    assert facility.phone == "+49 30 1"
    assert facility.website == "https://example.org"


def test_address_composition():
    assert build_address({}) is None
    assert build_address({"addr:full": "1 Main St, Town"}) == "1 Main St, Town"
    assert (
        build_address({"addr:street": "Main St", "addr:housenumber": "5", "addr:postcode": "123", "addr:city": "X"})
        == "Main St 5, 123 X"
    )


def test_shelter_flags(element_factory):
    bus, _ = normalize_element(element_factory(tags={"amenity": "shelter", "shelter_type": "public_transport"}), TS)
    assert "likely_not_emergency_shelter" in bus.quality_flags
    unknown, _ = normalize_element(element_factory(tags={"amenity": "shelter"}), TS)
    assert "shelter_type_unspecified" in unknown.quality_flags


def test_skip_reasons(element_factory):
    elements = [
        element_factory("node", 1),
        element_factory("node", 2, {"amenity": "cafe"}),
        element_factory("way", 3, center=False),
        {"type": "area", "id": 4, "tags": {"amenity": "hospital"}},
        {"type": "node", "id": "bad"},
        "not a dict",
    ]
    facilities, report = normalize_elements(elements, TS)
    assert [f.osm_id for f in facilities] == [1]
    assert report.total_elements == 6
    assert report.count("unclassified") == 1
    assert report.count("missing_coordinates") == 1
    assert report.count("unsupported_element") == 3


def test_allowed_categories_filter(element_factory):
    elements = [element_factory("node", 1, {"amenity": "fuel"}), element_factory("node", 2, {"amenity": "hospital"})]
    facilities, _ = normalize_elements(elements, TS, allowed_categories={"hospital"})
    assert [f.category for f in facilities] == ["hospital"]
