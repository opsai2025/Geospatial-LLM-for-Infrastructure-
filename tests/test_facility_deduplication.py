from models.facility import Facility
from processing.validate_facilities import deduplicate_by_source_id, flag_possible_duplicates, haversine_m


def fac(osm_type, osm_id, name="City Hospital", lat=52.5, lon=13.4, category="hospital"):
    return Facility(osm_type, osm_id, name, category, "Hospitals", lat, lon)


def test_same_type_and_id_is_deduplicated():
    records = [fac("node", 1), fac("node", 1), fac("way", 1), fac("node", 2)]
    unique, removed = deduplicate_by_source_id(records)
    assert [f.source_id for f in unique] == ["node/1", "way/1", "node/2"]
    assert removed == 1


def test_first_occurrence_is_kept():
    first, second = fac("node", 1, name="A"), fac("node", 1, name="B")
    unique, _ = deduplicate_by_source_id([first, second])
    assert unique == [first]


def test_node_and_way_of_same_facility_are_flagged_not_removed():
    node = fac("node", 1, lat=52.5000, lon=13.4000)
    way = fac("way", 2, name="  city   HOSPITAL ", lat=52.5003, lon=13.4002)
    records = [node, way]
    assert flag_possible_duplicates(records, max_distance_m=100) == 2
    assert len(records) == 2
    assert "possible_duplicate:way/2" in node.quality_flags
    assert "possible_duplicate:node/1" in way.quality_flags


def test_distant_or_different_category_not_flagged():
    a = fac("node", 1, lat=52.50, lon=13.40)
    far = fac("node", 2, lat=52.60, lon=13.40)
    other_category = fac("node", 3, lat=52.50, lon=13.40, category="pharmacy")
    unnamed = fac("node", 4, name=None)
    assert flag_possible_duplicates([a, far, other_category, unnamed], max_distance_m=100) == 0
    assert all(not f.quality_flags for f in (a, far, other_category, unnamed))


def test_flagging_is_idempotent():
    a, b = fac("node", 1), fac("way", 2)
    flag_possible_duplicates([a, b])
    flag_possible_duplicates([a, b])
    assert a.quality_flags == ["possible_duplicate:way/2"]


def test_haversine():
    # One degree of latitude is roughly 111.2 km.
    assert abs(haversine_m(0, 0, 1, 0) - 111_195) < 50
