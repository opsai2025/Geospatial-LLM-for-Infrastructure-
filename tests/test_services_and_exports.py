import csv
import io
import json

import pytest
import requests

import config
from exports.export_facilities import build_export_metadata, to_csv_bytes, to_geojson, to_json
from models.facility import Facility
from models.region import BBox
from services.facility_service import FacilityService
from services.http_client import (
    AllEndpointsFailedError,
    QueryTooLargeError,
    RateLimitError,
    ServiceError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    UnexpectedResponseError,
)
from services.overpass_client import OverpassClient, build_overpass_query, check_query_area
from visualization.facility_map import build_facility_map, facility_popup_html, render_map_html


class FakeResponse:
    def __init__(self, status=200, payload=None, text="", headers=None):
        self.status_code = status
        self._payload = payload
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.urls = []

    def request(self, method, url, **kwargs):
        self.calls += 1
        self.urls.append(url)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def client(*responses):
    return OverpassClient("https://example.test/api", session=FakeSession(responses), max_retries=1)


BERLIN = BBox(52.33, 13.08, 52.68, 13.76)


def test_query_contains_all_tags_and_bbox():
    query = build_overpass_query(BERLIN, ["hospital", "clinic", "police", "government"], timeout_s=60)
    assert query.startswith("[out:json][timeout:60];")
    assert 'nwr["amenity"~"^(hospital|clinic|doctors|police)$"](52.3300000,13.0800000,52.6800000,13.7600000);' in query
    assert 'nwr["office"="government"]' in query
    assert query.rstrip().endswith("out center tags;")


def test_query_rejects_empty_categories():
    with pytest.raises(ValueError):
        build_overpass_query(BERLIN, [])


def test_area_limit():
    assert check_query_area(BERLIN) > 0
    with pytest.raises(QueryTooLargeError):
        check_query_area(BBox(40.0, 0.0, 50.0, 20.0))
    with pytest.raises(QueryTooLargeError):
        check_query_area(BBox(10.0, 170.0, 20.0, -170.0))  # crosses antimeridian


def test_fetch_success():
    assert client(FakeResponse(payload={"elements": [{"type": "node"}]})).fetch("q") == [{"type": "node"}]


def test_server_side_timeout_remark_is_an_error():
    response = FakeResponse(payload={"elements": [], "remark": 'runtime error: Query timed out in "query"'})
    with pytest.raises(ServiceTimeoutError):
        client(response).fetch("q")


def test_out_of_memory_remark():
    response = FakeResponse(payload={"elements": [], "remark": "runtime error: Query run out of memory"})
    with pytest.raises(QueryTooLargeError):
        client(response).fetch("q")


def test_client_timeout():
    with pytest.raises(ServiceTimeoutError):
        client(requests.Timeout()).fetch("q")


def test_connection_error():
    with pytest.raises(ServiceUnavailableError):
        client(requests.ConnectionError()).fetch("q")


def test_rate_limit_retries_once_then_fails():
    c = client(FakeResponse(429, headers={"Retry-After": "0"}), FakeResponse(429, headers={"Retry-After": "0"}))
    with pytest.raises(RateLimitError):
        c.fetch("q")
    assert c.session.calls == 2


def test_retry_then_success():
    c = client(FakeResponse(503, headers={"Retry-After": "0"}), FakeResponse(payload={"elements": []}))
    assert c.fetch("q") == []
    assert c.session.calls == 2


def test_non_json_and_bad_shape():
    with pytest.raises(UnexpectedResponseError):
        client(FakeResponse(payload=None, headers={"Content-Type": "text/html"})).fetch("q")
    with pytest.raises(UnexpectedResponseError):
        client(FakeResponse(payload={"no_elements": True})).fetch("q")


PRIMARY = "https://primary.test/api/interpreter"
SECOND = "https://second.test/api/interpreter"
THIRD = "https://third.test/api/interpreter"


def multi_client(*responses, max_retries=0):
    return OverpassClient([PRIMARY, SECOND, THIRD], session=FakeSession(responses), max_retries=max_retries)


def test_fallback_to_second_endpoint_on_502():
    c = multi_client(FakeResponse(502), FakeResponse(payload={"elements": [{"type": "node"}]}))
    assert c.fetch_with_endpoint("q") == ([{"type": "node"}], SECOND)
    assert c.session.urls == [PRIMARY, SECOND]


@pytest.mark.parametrize("failure", [requests.ConnectionError(), requests.Timeout(), FakeResponse(503), FakeResponse(504)])
def test_fallback_on_connection_errors_timeouts_and_5xx(failure):
    c = multi_client(failure, FakeResponse(payload={"elements": []}))
    assert c.fetch_with_endpoint("q") == ([], SECOND)


def test_primary_endpoint_reported_when_it_answers():
    c = multi_client(FakeResponse(payload={"elements": []}))
    assert c.fetch_with_endpoint("q") == ([], PRIMARY)
    assert c.session.calls == 1


def test_all_endpoints_fail():
    c = multi_client(FakeResponse(502), requests.ConnectionError(), requests.Timeout())
    with pytest.raises(AllEndpointsFailedError) as info:
        c.fetch("q")
    exc = info.value
    assert isinstance(exc, ServiceUnavailableError)
    assert exc.endpoints == [PRIMARY, SECOND, THIRD]
    for url in (PRIMARY, SECOND, THIRD):
        assert url in str(exc)
    assert "HTTP 502" in str(exc) and "connection failed" in str(exc) and "timed out" in str(exc)


def test_fallback_attempts_are_bounded():
    retry = {"Retry-After": "0"}
    c = multi_client(*[FakeResponse(502, headers=retry) for _ in range(6)], max_retries=1)
    with pytest.raises(AllEndpointsFailedError):
        c.fetch("q")
    assert c.session.calls == 6  # 3 endpoints x (1 + 1 retry)
    assert c.session.urls == [PRIMARY, PRIMARY, SECOND, SECOND, THIRD, THIRD]


def test_bad_query_does_not_fall_over():
    c = multi_client(FakeResponse(400, text="parse error"), FakeResponse(payload={"elements": []}))
    with pytest.raises(ServiceError) as info:
        c.fetch("q")
    assert info.value.status_code == 400
    assert not isinstance(info.value, AllEndpointsFailedError)
    assert c.session.urls == [PRIMARY]


@pytest.mark.parametrize("response", [
    FakeResponse(payload={"elements": [], "remark": "runtime error: Query run out of memory"}),
    FakeResponse(429),
])
def test_server_side_failures_do_not_fall_over(response):
    c = multi_client(response, FakeResponse(payload={"elements": []}))
    with pytest.raises((QueryTooLargeError, RateLimitError)):
        c.fetch("q")
    assert c.session.urls == [PRIMARY]


def test_single_endpoint_raises_original_error():
    with pytest.raises(ServiceTimeoutError) as info:
        client(requests.Timeout()).fetch("q")
    assert not isinstance(info.value, AllEndpointsFailedError)


def test_facility_service_reports_answering_endpoint(bbox_only_region):
    element = {"type": "node", "id": 1, "lat": 52.5, "lon": 13.5, "tags": {"amenity": "hospital", "name": "H"}}
    c = multi_client(requests.ConnectionError(), FakeResponse(payload={"elements": [element]}))
    result = FacilityService(c).load(bbox_only_region, ["hospital"])
    assert result.source_endpoint == SECOND
    assert len(result.facilities) == 1


def test_overpass_url_config(monkeypatch):
    monkeypatch.delenv("GEOCRISIS_OVERPASS_URLS", raising=False)
    monkeypatch.delenv("GEOCRISIS_OVERPASS_URL", raising=False)
    assert config._overpass_urls() == config.DEFAULT_OVERPASS_URLS
    assert config.DEFAULT_OVERPASS_URLS[0] == "https://overpass-api.de/api/interpreter"
    monkeypatch.setenv("GEOCRISIS_OVERPASS_URL", PRIMARY)
    assert config._overpass_urls() == (PRIMARY,)
    monkeypatch.setenv("GEOCRISIS_OVERPASS_URLS", f" {SECOND}, {THIRD},,{SECOND} ")
    assert config._overpass_urls() == (SECOND, THIRD)


def sample_facilities():
    return [
        Facility(
            "node", 1, "Krankenhaus Ä", "hospital", "Hospitals", 52.5, 13.4,
            raw_tags={"amenity": "hospital", "name": "Krankenhaus Ä"}, retrieved_at="2026-10-19T00:00:00+00:00",
        ),
        Facility(
            "way", 2, None, "police", "Police stations", 52.51, 13.41,
            raw_tags={"amenity": "police"}, location_precision="osm_way_center",
            retrieved_at="2026-10-19T00:00:00+00:00", quality_flags=["missing_name"],
        ),
    ]


def test_csv_export():
    rows = list(csv.DictReader(io.StringIO(to_csv_bytes(sample_facilities()).decode("utf-8-sig"))))
    assert len(rows) == 2
    assert rows[0]["source_id"] == "node/1"
    assert rows[0]["name"] == "Krankenhaus Ä"
    assert rows[1]["name"] == ""
    assert rows[1]["quality_flags"] == "missing_name"
    assert json.loads(rows[0]["raw_tags_json"]) == {"amenity": "hospital", "name": "Krankenhaus Ä"}
    for column in ("osm_type", "osm_id", "category", "latitude", "longitude", "source", "retrieved_at"):
        assert rows[0][column]


def test_geojson_export():
    metadata = build_export_metadata(region_name="Berlin", retrieved_at="t")
    collection = to_geojson(sample_facilities(), metadata)
    json.dumps(collection)  # serializable
    assert collection["type"] == "FeatureCollection"
    feature = collection["features"][0]
    assert feature["geometry"] == {"type": "Point", "coordinates": [13.4, 52.5]}
    assert feature["id"] == "node/1"
    assert feature["properties"]["raw_tags"]["amenity"] == "hospital"
    assert feature["properties"]["source"] == "OpenStreetMap"
    assert collection["metadata"]["operational_status"] == "not verified"


def test_json_export():
    data = to_json(sample_facilities(), build_export_metadata())
    assert data["count"] == 2
    assert data["facilities"][1]["name"] is None
    assert data["facilities"][1]["raw_tags"] == {"amenity": "police"}


def test_map_builds_and_escapes_html(square_region):
    facilities = sample_facilities()
    facilities[0].name = "<script>alert(1)</script>"
    facilities[0].website = "javascript:alert(1)"
    popup = facility_popup_html(facilities[0])
    assert "<script>" not in popup
    assert "href='javascript" not in popup
    assert "تأیید نشده" in popup
    html = build_facility_map(facilities, square_region).get_root().render()
    for layer in ("بیمارستان‌ها (۱)", "کلانتری‌ها و مراکز پلیس (۱)"):
        # folium writes layer names into its JavaScript with \u escapes
        assert layer in html or json.dumps(layer)[1:-1] in html
    assert "OpenStreetMap" in html


def test_render_map_html_is_standalone(square_region):
    facilities = sample_facilities()
    first = render_map_html(facilities, square_region)
    assert first.lstrip().lower().startswith("<!doctype html>")
    assert "leaflet" in first.lower()
    assert first.count("L.marker(") == 2


def test_map_has_fullscreen_toggle(square_region):
    html = render_map_html([], square_region)
    assert "requestFullscreen" in html and "exitFullscreen" in html
    assert "fullscreenchange" in html
    assert "fullscreenEnabled" in html and "frameElement" in html  # native mode, else window-filling fallback
    assert "Escape" in html
    assert "خروج از تمام‌صفحه" in html


def test_map_has_resize_guard(square_region):
    html = render_map_html([], square_region)
    assert "ResizeObserver" in html and "invalidateSize" in html
    assert 'window.addEventListener("load"' in html
