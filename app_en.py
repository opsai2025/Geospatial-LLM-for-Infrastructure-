"""English interface for GeoCrisis Agent. Run: streamlit run app_en.py"""

from __future__ import annotations

import html
import os
import re

import pandas as pd
import streamlit as st

import config
from exports.export_facilities import build_export_metadata, facilities_to_dataframe, to_csv_bytes, to_geojson_bytes, to_json_bytes
from models.region import Region
from services.facility_service import FacilityResult, build_result, utc_now_iso
from services.http_client import ServiceError
from services.overpass_client import OverpassClient, build_overpass_query, check_query_area
from services.region_search import NominatimClient
from ui.en_theme import apply_english_theme
from visualization.facility_map import render_map_html

st.set_page_config(page_title="GeoCrisis | Infrastructure intelligence", page_icon="🌐", layout="wide", initial_sidebar_state="expanded")
apply_english_theme()


def markup(content: str) -> None:
    st.markdown(content, unsafe_allow_html=True)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


@st.cache_resource
def nominatim() -> NominatimClient:
    # Prefer English place names while still accepting queries in any language.
    return NominatimClient(language=os.environ.get("GEOCRISIS_NOMINATIM_LANGUAGE", "").strip() or "en")


@st.cache_resource
def overpass() -> OverpassClient:
    return OverpassClient()


@st.cache_data(ttl=config.GEOCODE_CACHE_TTL_S, max_entries=200, show_spinner=False)
def search_regions(query: str) -> list[Region]:
    return nominatim().search(query)


@st.cache_data(ttl=config.FACILITY_CACHE_TTL_S, max_entries=30, show_spinner=False)
def fetch_elements(query: str) -> tuple[list[dict], str, str]:
    retrieved_at = utc_now_iso()
    elements, endpoint = overpass().fetch_with_endpoint(query)
    return elements, retrieved_at, endpoint


for name, value in {
    "en_regions": None, "en_search_query": "", "en_search_error": None,
    "en_result": None, "en_load_error": None, "en_map_cache": None,
}.items():
    st.session_state.setdefault(name, value)
for category in config.CATEGORIES:
    st.session_state.setdefault(f"en_cat_{category}", True)


def select_all_categories(value: bool) -> None:
    for category in config.CATEGORIES:
        st.session_state[f"en_cat_{category}"] = value


def run_search(query: str) -> None:
    query = re.sub(r"\s+", " ", query or "").strip()
    st.session_state.en_search_query = query
    st.session_state.en_search_error = None
    st.session_state.pop("en_region_select", None)
    if not query:
        st.session_state.en_regions = None
        st.session_state.en_search_error = "Enter a city, municipality, or region to search."
        return
    try:
        with st.spinner("Finding matching places…"):
            regions = search_regions(query)
    except ServiceError as exc:
        st.session_state.en_regions = None
        st.session_state.en_search_error = exc.user_message
        return
    st.session_state.en_regions = regions
    if not regions:
        st.session_state.en_search_error = "No matching places found. Check the spelling or add a country name."


def run_load(region: Region, categories: list[str], *, fresh: bool = False) -> None:
    st.session_state.en_load_error = None
    try:
        check_query_area(region.bbox)
        query = build_overpass_query(region.bbox, categories)
        if fresh:
            fetch_elements.clear()
        with st.spinner("Finding facilities in OpenStreetMap. Larger areas may take a little longer…"):
            elements, retrieved_at, endpoint = fetch_elements(query)
        st.session_state.en_result = build_result(
            region, categories, elements, retrieved_at=retrieved_at, source_endpoint=endpoint, query=query
        )
    except ServiceError as exc:
        st.session_state.en_result = None
        st.session_state.en_load_error = exc.user_message
    except ValueError as exc:
        st.session_state.en_result = None
        st.session_state.en_load_error = str(exc)


def show_map(facilities, region: Region, token: str, *, height: int = 560) -> None:
    cached = st.session_state.en_map_cache
    if cached and cached[0] == token:
        map_html = cached[1]
    else:
        map_html = render_map_html(facilities, region, locale="en")
        st.session_state.en_map_cache = (token, map_html)
    if hasattr(st, "iframe"):
        st.iframe(map_html, height=height)
    else:
        import streamlit.components.v1 as components
        components.html(map_html, height=height)


def section(title: str, description: str, *, chip: str = "") -> None:
    badge = f"<span class='en-chip'>{esc(chip)}</span>" if chip else ""
    markup(f"<div class='en-heading'><div><h2>{esc(title)}</h2><p>{esc(description)}</p></div>{badge}</div>")


def notice(body: str, *, title: str = "A note on the data") -> None:
    markup(f"<div class='en-notice'><strong>{esc(title)}</strong><br>{esc(body)}</div>")


def stats(items: list[tuple[str, str, str]]) -> None:
    cards = "".join(
        f"<div class='en-stat'><div class='en-stat-label'>{esc(label)}</div>"
        f"<div class='en-stat-value'>{esc(value)}</div><div class='en-stat-hint'>{esc(hint)}</div></div>"
        for label, value, hint in items
    )
    markup(f"<div class='en-stats'>{cards}</div>")


def category_bars(counts: dict[str, int]) -> None:
    peak = max(counts.values(), default=0) or 1
    rows = "".join(
        f"<div class='en-bar'><div class='en-bar-head'><span>{esc(config.CATEGORIES[key].label)}</span>"
        f"<b>{count:,}</b></div><div class='en-track'><div class='en-fill' style='width:{100 * count / peak:.1f}%'></div></div></div>"
        for key, count in counts.items()
    )
    markup("<div class='en-bars'><div class='en-bars-title'>Facilities by category</div>" + rows +
           "<div class='en-bars-foot'>A zero means no records were found in OSM, not that no facilities exist.</div></div>")


# Sidebar: region selection, categories and exports.
selected_region: Region | None = None
with st.sidebar:
    markup("<div class='en-brand'><div class='en-brand-mark'>◈</div><div><div class='en-brand-name'>GeoCrisis</div>"
           "<div class='en-brand-sub'>Infrastructure intelligence</div></div></div>")
    markup("<div class='en-side-kicker'>01 / Select a region</div>")
    with st.form("en_region_search", border=False):
        query_text = st.text_input("City, municipality or region", value=st.session_state.en_search_query,
                                   placeholder="e.g. Cambridge, UK")
        search_clicked = st.form_submit_button("Search places", icon=":material/search:", type="primary", width="stretch")
    if search_clicked:
        run_search(query_text)
    if st.session_state.en_search_error:
        st.warning(st.session_state.en_search_error)
    regions: list[Region] | None = st.session_state.en_regions
    if regions:
        if len(regions) > 1:
            selected_region = st.selectbox("Choose a matching place", regions, format_func=lambda region: region.label,
                                           key="en_region_select")
        else:
            selected_region = regions[0]
        st.success(selected_region.display_name, icon=":material/location_on:")
        if selected_region.has_boundary:
            st.caption("Administrative boundary available · results will be clipped to it.")
        else:
            st.warning("No administrative boundary is available. Results may include nearby places inside the bounding box.")
        if selected_region.bbox.area_km2() > config.MAX_QUERY_AREA_KM2:
            st.error(f"This area exceeds the {config.MAX_QUERY_AREA_KM2:,.0f} km² query limit. Choose a smaller region.")
    else:
        markup("<div class='en-side-note'>Start with a place. You can refine the search before loading any data.</div>")

    markup("<div class='en-side-kicker'>02 / Choose categories</div>")
    col_all, col_clear = st.columns(2)
    col_all.button("Select all", on_click=select_all_categories, args=(True,), width="stretch")
    col_clear.button("Clear", on_click=select_all_categories, args=(False,), width="stretch")
    selected_categories = [key for key, definition in config.CATEGORIES.items()
                           if st.checkbox(definition.label, key=f"en_cat_{key}")]

    markup("<div class='en-side-kicker'>03 / Explore</div>")
    has_result = st.session_state.en_result is not None
    load_clicked = st.button("Update facilities" if has_result else "Find facilities", icon=":material/travel_explore:",
                             type="primary", disabled=selected_region is None or not selected_categories, width="stretch")
    fresh_clicked = False
    if has_result:
        fresh_clicked = st.button("Fetch fresh data", icon=":material/refresh:",
                                  disabled=selected_region is None or not selected_categories, width="stretch")
    if selected_region is not None and not selected_categories:
        st.caption("Select at least one facility category.")

if (load_clicked or fresh_clicked) and selected_region is not None and selected_categories:
    run_load(selected_region, selected_categories, fresh=fresh_clicked)
    st.rerun()

result: FacilityResult | None = st.session_state.en_result
with st.sidebar:
    markup("<div class='en-side-kicker'>04 / Export</div>")
    if result is None:
        markup("<div class='en-side-note'>CSV, GeoJSON, and JSON downloads appear after facilities are loaded.</div>")
    else:
        metadata = build_export_metadata(region_name=result.region.display_name, region_id=result.region.key,
            boundary_mode=result.boundary_mode, category_keys=result.category_keys, retrieved_at=result.retrieved_at,
            source_endpoint=result.source_endpoint)
        stem = f"facilities_{result.region.osm_type}_{result.region.osm_id}" if result.region.osm_type and result.region.osm_id is not None else "facilities"
        st.download_button("Download CSV", to_csv_bytes(result.facilities), f"{stem}.csv", "text/csv", width="stretch")
        st.download_button("Download GeoJSON", to_geojson_bytes(result.facilities, metadata), f"{stem}.geojson", "application/geo+json", width="stretch")
        st.download_button("Download JSON", to_json_bytes(result.facilities, metadata), f"{stem}.json", "application/json", width="stretch")
        st.caption("Data © OpenStreetMap contributors · ODbL")

markup("<div class='en-hero'><div class='en-eyebrow'>Geospatial intelligence &nbsp; / &nbsp; Stage 01</div>"
       "<h1>Know your critical<br>infrastructure.</h1>"
       "<p>Discover essential services, explore their spatial context, and turn open geographic data into a clearer operational picture.</p>"
       "<div class='en-hero-tags'><span>OpenStreetMap data</span><span>10 facility categories</span><span>GIS-ready exports</span></div></div>")

if st.session_state.en_load_error:
    st.error("Could not load facilities: " + st.session_state.en_load_error)
    st.info("Try a smaller area or fewer categories, or try again when the service is available.")

if result is None:
    section("A clearer picture starts here", "From a place name to a map you can explore.", chip="Getting started")
    markup("<div class='en-steps'>"
           "<div class='en-step'><span class='en-step-num'>01</span><h3>Find your area</h3><p>Search for a city or region and choose the right match.</p></div>"
           "<div class='en-step'><span class='en-step-num'>02</span><h3>Choose what matters</h3><p>Focus on hospitals, emergency services, public offices, and more.</p></div>"
           "<div class='en-step'><span class='en-step-num'>03</span><h3>Explore and export</h3><p>Review the map and data quality, then take the results into your GIS.</p></div></div>")
    notice(config.STATUS_DISCLAIMER, title="Open data, interpreted carefully")
    if selected_region is not None:
        section("Region preview", selected_region.display_name, chip="Selected area")
        show_map([], selected_region, f"preview:{selected_region.key}")
    st.stop()

if selected_region is None or selected_region.key != result.region.key:
    st.info(f"Showing results for {result.region.display_name}. Select a region and update facilities to change them.")
elif set(selected_categories) != set(result.category_keys):
    st.info("Category selection changed. Select Update facilities to apply it to the displayed results.")

report = result.report
counts = result.category_counts()
covered = sum(count > 0 for count in counts.values())
section("Your area at a glance", result.region.display_name, chip="OpenStreetMap")
stats([
    ("Mapped facilities", f"{report.final_count:,}", "Records in this area"),
    ("Categories represented", f"{covered} / {len(counts)}", "With at least one record"),
    ("Spatial filter", "Boundary" if result.boundary_mode == "boundary" else "Bounding box", "Administrative area" if result.boundary_mode == "boundary" else "Approximate extent"),
    ("Unnamed records", f"{report.unnamed:,}", "Flagged for review"),
])
notice(config.STATUS_DISCLAIMER)
for warning in result.warnings:
    st.warning(warning)

tab_map, tab_table, tab_quality, tab_guide = st.tabs(["Map & insights", "Facility table", "Data quality", "Guide"])
with tab_map:
    map_col, chart_col = st.columns([3.3, 1.2], gap="medium")
    with map_col:
        st.caption(f"{result.region.display_name} · Retrieved {result.retrieved_at}")
        show_map(result.facilities, result.region,
                 f"result:{result.region.key}:{result.retrieved_at}:{','.join(result.category_keys)}", height=630)
    with chart_col:
        category_bars(counts)


@st.fragment
def facility_table(data: FacilityResult) -> None:
    frame = facilities_to_dataframe(data.facilities)
    filters = st.columns([2, 1])
    query = filters[0].text_input("Search facilities", placeholder="Name, address, operator, or OSM ID", key="en_table_search")
    categories = filters[1].multiselect("Filter categories", options=[config.CATEGORIES[k].label for k in data.category_keys],
                                        placeholder="All categories", key="en_table_categories")
    filtered = frame.copy()
    if query.strip():
        mask = pd.Series(False, index=filtered.index)
        for column in ("name", "address", "operator", "source_id", "category_label", "phone"):
            mask |= filtered[column].fillna("").astype(str).str.contains(query.strip(), case=False, regex=False)
        filtered = filtered[mask]
    if categories:
        filtered = filtered[filtered["category_label"].isin(categories)]
    columns = ["name", "category_label", "address", "operator", "phone", "location_precision", "quality_flags", "latitude", "longitude", "source_id", "osm_url"]
    st.dataframe(filtered[columns], hide_index=True, width="stretch", height=500,
        column_config={"name": "Name", "category_label": "Category", "address": "Address", "operator": "Operator",
                       "phone": "Phone", "location_precision": "Position precision", "quality_flags": "Quality flags",
                       "latitude": "Latitude", "longitude": "Longitude", "source_id": "OSM ID",
                       "osm_url": st.column_config.LinkColumn("OpenStreetMap", display_text="View")})
    st.caption(f"Showing {len(filtered):,} of {len(frame):,} records. Filters do not change the map or downloads.")


with tab_table:
    facility_table(result)

with tab_quality:
    section("Processing details", "How the raw OpenStreetMap records became this result.")
    rows = [
        ("Raw elements received", report.total_elements), ("Unsupported elements", report.unsupported),
        ("Unclassified elements", report.unclassified), ("Missing coordinates", report.missing_coordinates),
        ("Invalid coordinates", report.invalid_coordinates), ("Repeated OSM elements removed", report.duplicates_removed),
        ("Outside the selected area", report.outside_region), ("Unnamed records", report.unnamed),
        ("Possible duplicates flagged", report.possible_duplicates), ("Final facilities", report.final_count),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Processing step", "Records"]), hide_index=True, width="stretch")
    st.caption("Possible duplicates are flagged, not removed. Way and relation centers are approximate and may not be entrances.")
    with st.expander("Data source and query"):
        st.write("Source endpoint:", result.source_endpoint)
        st.write("Retrieved:", result.retrieved_at)
        st.write("Spatial filter:", result.boundary_mode)
        st.code(result.query, language="text")

with tab_guide:
    section("Using the workspace", "A short guide to the map and your exports.")
    st.markdown("""
    1. Search for a place and select the correct match in the sidebar.
    2. Choose the facility categories and select **Find facilities**.
    3. Explore map layers, review individual markers, and filter the facility table.
    4. Check data quality, then download CSV, GeoJSON, or JSON for further work.

    Markers for OSM areas are approximate centers. The table filters do not affect the map or exports.
    Place searches are cached for 24 hours and facility results for 6 hours; **Fetch fresh data** bypasses the facility cache.
    """)
    notice(config.STATUS_DISCLAIMER, title="About this data")
