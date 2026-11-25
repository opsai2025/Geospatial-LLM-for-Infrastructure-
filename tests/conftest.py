import pytest

from models.region import BBox, Region
from shapely.geometry import box


def make_element(osm_type="node", osm_id=1, tags=None, lat=52.52, lon=13.40, center=True):
    element = {"type": osm_type, "id": osm_id, "tags": tags if tags is not None else {"amenity": "hospital"}}
    if osm_type == "node":
        element.update({"lat": lat, "lon": lon})
    elif center:
        element["center"] = {"lat": lat, "lon": lon}
    return element


@pytest.fixture
def element_factory():
    return make_element


@pytest.fixture
def square_region():
    """Region whose boundary is the square lon 13.0–14.0, lat 52.0–53.0 inside a larger bbox."""
    return Region(
        display_name="Test Region",
        latitude=52.5,
        longitude=13.5,
        bbox=BBox(south=51.5, west=12.5, north=53.5, east=14.5),
        boundary=box(13.0, 52.0, 14.0, 53.0),
        osm_type="relation",
        osm_id=42,
    )


@pytest.fixture
def bbox_only_region():
    return Region(
        display_name="Point Place",
        latitude=52.5,
        longitude=13.5,
        bbox=BBox(south=52.0, west=13.0, north=53.0, east=14.0),
        boundary=None,
        osm_type="node",
        osm_id=7,
    )
