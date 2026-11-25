"""Exercise the English workspace without contacting public map services."""

from pathlib import Path

from shapely.geometry import box
from streamlit.testing.v1 import AppTest

from models.facility import Facility
from models.region import BBox, Region
from services.overpass_client import OverpassClient
from services.region_search import NominatimClient
from visualization.facility_map import facility_popup_html, render_map_html


def test_english_map_localizes_layers_popups_and_controls():
    region = Region("Example area", 52.52, 13.40, BBox(52.50, 13.38, 52.54, 13.44))
    facility = Facility("node", 1, "Example Hospital", "hospital", "Hospitals", 52.52, 13.40)
    english = render_map_html([facility], region, locale="en")
    assert "Hospitals (1)" in english
    assert "Bounding box" in english
    assert "Full screen" in english
    assert "operational status is not verified" in facility_popup_html(facility, locale="en")
    assert "وضعیت فعالیت تأیید نشده است" in facility_popup_html(facility)


def test_english_search_load_and_table_filter(monkeypatch):
    region = Region("Test City", 52.52, 13.40, BBox(52.50, 13.38, 52.54, 13.44),
                    boundary=box(13.38, 52.50, 13.44, 52.54), osm_type="relation", osm_id=123)
    elements = [{"type": "node", "id": 101, "lat": 52.52, "lon": 13.40,
                 "tags": {"amenity": "hospital", "name": "Example Hospital"}}]
    monkeypatch.setattr(NominatimClient, "search", lambda self, query: [region])
    monkeypatch.setattr(OverpassClient, "fetch_with_endpoint", lambda self, query: (elements, "https://example.test"))

    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app_en.py", default_timeout=20).run()
    assert not app.exception
    assert app.button[0].label == "Search places"
    app.text_input[0].input("Test City")
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["en_regions"][0].display_name == "Test City"
    next(button for button in app.button if button.label == "Find facilities").click().run()
    assert not app.exception
    result = app.session_state["en_result"]
    assert [item.name for item in result.facilities] == ["Example Hospital"]
    assert [tab.label for tab in app.tabs] == ["Map & insights", "Facility table", "Data quality", "Guide"]
    app.text_input(key="en_table_search").input("not a match").run()
    assert not app.exception
    assert any("Showing 0 of 1 records" in caption.value for caption in app.caption)
