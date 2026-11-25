"""GeoCrisis Agent — Stage 1: essential facility discovery and mapping.

Persian (RTL) user interface. Run with:  streamlit run app.py
"""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

import config
from exports.export_facilities import (
    build_export_metadata,
    facilities_to_dataframe,
    to_csv_bytes,
    to_geojson_bytes,
    to_json_bytes,
)
from models.region import Region
from services.facility_service import FacilityResult, build_result, utc_now_iso
from services.http_client import QueryTooLargeError, ServiceError, ServiceTimeoutError
from services.overpass_client import OverpassClient, build_overpass_query, check_query_area
from services.region_search import NominatimClient
from ui import components as ui
from ui import i18n_fa as fa
from ui.persian import fa_digits, format_jalali_datetime
from ui.theme import apply_theme
from visualization.facility_map import render_map_html

st.set_page_config(
    page_title="سامانه تأسیسات حیاتی",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()


# --------------------------------------------------------------------------
# Cached service access
# --------------------------------------------------------------------------
@st.cache_resource
def get_nominatim() -> NominatimClient:
    return NominatimClient()


@st.cache_resource
def get_overpass() -> OverpassClient:
    return OverpassClient()


@st.cache_data(ttl=config.GEOCODE_CACHE_TTL_S, max_entries=200, show_spinner=False)
def search_regions(query: str) -> list[Region]:
    return get_nominatim().search(query)


@st.cache_data(ttl=config.FACILITY_CACHE_TTL_S, max_entries=30, show_spinner=False)
def fetch_elements(query: str) -> tuple[list[dict], str, str]:
    """Run an Overpass query; return (elements, retrieved_at, answering endpoint).

    Failures raise and are therefore never cached.
    """
    retrieved_at = utc_now_iso()
    elements, endpoint = get_overpass().fetch_with_endpoint(query)
    return elements, retrieved_at, endpoint


def normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
defaults = {
    "regions": None,  # list[Region] | None
    "search_query": "",
    "search_message": None,  # (box kind, text, technical detail)
    "result": None,  # FacilityResult | None
    "load_error": None,  # (kind, text, technical detail)
    "map_cache": None,  # (token, map HTML)
}
for name, value in defaults.items():
    st.session_state.setdefault(name, value)
for key in config.CATEGORIES:
    st.session_state.setdefault(f"cat_{key}", True)


def set_all_categories(value: bool) -> None:
    for key in config.CATEGORIES:
        st.session_state[f"cat_{key}"] = value


def run_search(query: str) -> None:
    st.session_state.search_query = query
    st.session_state.search_message = None
    st.session_state.pop("region_select", None)
    if not query:
        st.session_state.regions = None
        st.session_state.search_message = ("amber", "لطفاً نام یک شهر، شهرستان یا منطقه را وارد کنید.", None)
        return
    try:
        with st.spinner("در حال جستجوی منطقه…"):
            regions = search_regions(query)
    except ServiceError as exc:
        st.session_state.regions = None
        st.session_state.search_message = (
            "red",
            "جستجوی منطقه انجام نشد. " + fa.service_error_message(exc),
            exc.user_message,
        )
        return
    st.session_state.regions = regions
    if not regions:
        st.session_state.search_message = (
            "amber",
            f"منطقه‌ای با نام «{query}» یافت نشد. املای نام را بررسی کنید، نام کشور را اضافه کنید "
            "یا نام انگلیسی منطقه را امتحان کنید.",
            None,
        )


def run_load(region: Region, category_keys: list[str], *, fresh: bool = False) -> None:
    st.session_state.load_error = None
    try:
        check_query_area(region.bbox)
        query = build_overpass_query(region.bbox, category_keys)
        if fresh:
            fetch_elements.clear()
        with st.spinner("در حال دریافت تأسیسات از OpenStreetMap… برای شهرهای بزرگ ممکن است تا یک دقیقه طول بکشد."):
            elements, retrieved_at, endpoint = fetch_elements(query)
        st.session_state.result = build_result(
            region,
            category_keys,
            elements,
            retrieved_at=retrieved_at,
            source_endpoint=endpoint,
            query=query,
        )
    except ServiceError as exc:
        if isinstance(exc, QueryTooLargeError):
            kind = "too_large"
        elif isinstance(exc, ServiceTimeoutError):
            kind = "timeout"
        else:
            kind = "error"
        st.session_state.result = None
        st.session_state.load_error = (
            kind,
            "دریافت تأسیسات انجام نشد. " + fa.service_error_message(exc, area_km2=region.bbox.area_km2()),
            exc.user_message,
        )
    except ValueError as exc:
        st.session_state.result = None
        st.session_state.load_error = ("error", "درخواست نامعتبر است؛ حداقل یک دسته را انتخاب کنید.", str(exc))


def show_map(facilities, region: Region | None, token: str, height: int) -> None:
    """Embed the map as static HTML, built once per token.

    The HTML string is identical on every rerun, so the browser keeps the
    already-loaded map instead of re-creating it (which could leave it blank).
    """
    cached = st.session_state.map_cache
    if cached and cached[0] == token:
        map_html = cached[1]
    else:
        map_html = render_map_html(facilities, region)
        st.session_state.map_cache = (token, map_html)
    if hasattr(st, "iframe"):  # newer Streamlit; components.html is deprecated there
        st.iframe(map_html, height=height)
    else:
        import streamlit.components.v1 as components

        components.html(map_html, height=height)


def export_stem(region: Region) -> str:
    if region.osm_type and region.osm_id is not None:
        return f"facilities_{region.osm_type}_{region.osm_id}"
    return "facilities"


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
selected_region: Region | None = None
load_clicked = fresh_clicked = False

with st.sidebar:
    ui.brand(fa.BRAND_TITLE, fa.BRAND_SUBTITLE)

    ui.side_title("🔎", "۱. انتخاب منطقه")
    with st.form("region_search_form", border=False):
        query_text = st.text_input(
            "نام شهر، شهرستان یا منطقه",
            value=st.session_state.search_query,
            placeholder="مثلاً: تهران، اصفهان، شیراز",
        )
        search_clicked = st.form_submit_button(
            "جستجوی منطقه", icon=":material/search:", type="primary", width="stretch"
        )
    if search_clicked:
        run_search(normalize_query(query_text))

    if st.session_state.search_message:
        kind, text, technical = st.session_state.search_message
        ui.box(kind, text, technical=technical)

    regions: list[Region] | None = st.session_state.regions
    if regions is None and not st.session_state.search_message:
        ui.side_note("برای شروع، نام منطقهٔ موردنظر را جستجو کنید.")
    elif regions:
        if len(regions) > 1:
            ui.side_note(f"{fa_digits(len(regions))} مکان مشابه یافت شد؛ مکان درست را انتخاب کنید:")
            index = st.radio(
                "مکان‌های یافت‌شده",
                options=list(range(len(regions))),
                format_func=lambda i: fa.region_option_label(regions[i]),
                key="region_select",
                label_visibility="collapsed",
            )
        else:
            index = 0
        selected_region = regions[index]
        ui.side_region(selected_region.display_name)
        if selected_region.has_boundary:
            ui.box("green", "مرز اداری در دسترس است؛ نتایج دقیقاً به مرز منطقه محدود می‌شوند.", icon="✅")
        else:
            ui.box(
                "amber",
                "مرز اداری این مکان در دسترس نیست؛ نتایج به کادر محدوده محدود می‌شوند و ممکن است شامل "
                "مکان‌های مجاور خارج از منطقه باشند.",
                icon="⚠️",
            )
        area = selected_region.bbox.area_km2()
        ui.side_note(f"مساحت تقریبی کادر محدوده: {fa_digits(round(area))} کیلومتر مربع")
        if area > config.MAX_QUERY_AREA_KM2:
            ui.box(
                "red",
                f"این منطقه از سقف {fa_digits(round(config.MAX_QUERY_AREA_KM2))} کیلومتر مربع بزرگ‌تر است؛ "
                "لطفاً منطقهٔ کوچک‌تری انتخاب کنید.",
            )

    ui.side_title("🏷️", "۲. دسته‌های تأسیسات")
    col_a, col_b = st.columns(2)
    col_a.button("انتخاب همه", icon=":material/done_all:", on_click=set_all_categories, args=(True,), width="stretch")
    col_b.button("حذف همه", icon=":material/remove_done:", on_click=set_all_categories, args=(False,), width="stretch")
    selected_categories = [
        key
        for key, definition in config.CATEGORIES.items()
        if st.checkbox(f"{definition.ui_icon} {definition.label_fa}", key=f"cat_{key}")
    ]

    ui.side_title("📥", "۳. دریافت داده")
    has_result = st.session_state.result is not None
    load_clicked = st.button(
        "به‌روزرسانی تأسیسات" if has_result else "بارگذاری تأسیسات",
        icon=":material/refresh:" if has_result else ":material/cloud_download:",
        type="primary",
        disabled=selected_region is None or not selected_categories,
        width="stretch",
        help="در صورت تکرار همان درخواست، از نتایج ذخیره‌شدهٔ اخیر استفاده می‌شود.",
    )
    if has_result:
        fresh_clicked = st.button(
            "دریافت دادهٔ تازه (بدون حافظهٔ موقت)",
            icon=":material/cloud_sync:",
            disabled=selected_region is None or not selected_categories,
            width="stretch",
        )
    if selected_region is not None and not selected_categories:
        ui.side_note("حداقل یک دسته را انتخاب کنید.")

if (load_clicked or fresh_clicked) and selected_region is not None and selected_categories:
    run_load(selected_region, selected_categories, fresh=fresh_clicked)
    st.rerun()  # redraw the sidebar so its buttons reflect the new result

result: FacilityResult | None = st.session_state.result

with st.sidebar:
    ui.side_title("💾", "۴. خروجی داده")
    if result is None:
        ui.side_note("پس از بارگذاری تأسیسات، دریافت خروجی فعال می‌شود.")
    else:
        metadata = build_export_metadata(
            region_name=result.region.display_name,
            region_id=result.region.key,
            boundary_mode=result.boundary_mode,
            category_keys=result.category_keys,
            retrieved_at=result.retrieved_at,
            source_endpoint=result.source_endpoint,
        )
        stem = export_stem(result.region)
        st.download_button(
            "جدول CSV", to_csv_bytes(result.facilities), f"{stem}.csv", "text/csv",
            icon=":material/table_view:", width="stretch",
        )
        st.download_button(
            "لایهٔ مکانی GeoJSON", to_geojson_bytes(result.facilities, metadata), f"{stem}.geojson",
            "application/geo+json", icon=":material/map:", width="stretch",
        )
        st.download_button(
            "دادهٔ کامل JSON", to_json_bytes(result.facilities, metadata), f"{stem}.json", "application/json",
            icon=":material/data_object:", width="stretch",
        )
        ui.side_note(f"{fa_digits(len(result.facilities))} رکورد · داده‌ها © مشارکت‌کنندگان OpenStreetMap (ODbL)")

# --------------------------------------------------------------------------
# Main area
# --------------------------------------------------------------------------
ui.header(fa.APP_TITLE, fa.APP_SUBTITLE)

if st.session_state.load_error:
    kind, text, technical = st.session_state.load_error
    ui.box("red", text, title="خطا در دریافت داده", icon="⛔", technical=technical)
    ui.box(
        "amber",
        [
            "دوباره روی «بارگذاری تأسیسات» کلیک کنید (ممکن است سرور موقتاً شلوغ باشد).",
            "تعداد دسته‌های انتخاب‌شده را کم کنید.",
            "منطقهٔ کوچک‌تری (مثلاً یک شهر یا بخش) جستجو کنید.",
        ],
        title="پیشنهادها",
        icon="💡",
    )

if result is None:
    ui.box("green", fa.GUIDE_STEPS, title="راهنمای استفاده", icon="📌", ordered=True)
    if selected_region is not None:
        ui.section("🗺️", "پیش‌نمایش منطقه", selected_region.display_name)
        show_map([], selected_region, f"preview:{selected_region.key}", height=620)
    st.stop()

# Notices when the sidebar no longer matches what is displayed
if selected_region is not None and selected_region.key != result.region.key:
    ui.box(
        "blue",
        f"نتایج نمایش‌داده‌شده مربوط به «{result.region.display_name}» است. برای منطقهٔ جدید روی "
        "«به‌روزرسانی تأسیسات» کلیک کنید.",
        icon="🔄",
    )
elif set(selected_categories) != set(result.category_keys):
    ui.box("blue", "انتخاب دسته‌ها تغییر کرده است؛ برای اعمال آن روی «به‌روزرسانی تأسیسات» کلیک کنید.", icon="🔄")

# ---- Status summary (cards first, then charts, then tables) -----------------
report = result.report
counts = result.category_counts()
with_results = sum(1 for c in counts.values() if c)
important_warnings, quality_warnings = fa.result_warnings(result)

ui.section("📍", result.region.display_name)
ui.box(
    "blue",
    [
        "منبع داده: OpenStreetMap از طریق سرویس Overpass",
        fa.endpoint_line(result.source_endpoint),
        f"زمان دریافت: {format_jalali_datetime(result.retrieved_at)}",
        "محدودهٔ مکانی: " + ("مرز اداری منطقه" if result.boundary_mode == "boundary" else "فقط کادر محدوده"),
        f"شناسهٔ منطقه در OSM: {result.region.key}",
    ],
    title="وضعیت داده",
    icon="🗂️",
)
for warning in important_warnings:
    ui.box("amber", warning, icon="⚠️")

unnamed_share = (report.unnamed / report.final_count) if report.final_count else 0.0
excluded = report.outside_region + report.invalid_coordinates + report.missing_coordinates
all_covered = with_results == len(counts)
ui.cards(
    [
        ui.Card(
            "🏥", "تعداد کل تأسیسات", fa_digits(report.final_count),
            tone="good" if report.final_count else "bad",
            hint=f"در {fa_digits(with_results)} دسته",
            badge="ثبت‌شده" if report.final_count else "بدون نتیجه",
        ),
        ui.Card(
            "🗂️", "پوشش دسته‌ها", f"{fa_digits(with_results)} از {fa_digits(len(counts))}",
            tone="good" if all_covered else ("warn" if with_results else "bad"),
            hint="دسته‌های دارای حداقل یک مورد ثبت‌شده",
            badge="کامل" if all_covered else ("ناقص" if with_results else "بدون نتیجه"),
        ),
        ui.Card(
            "🧭", "محدودهٔ مکانی", "مرز اداری" if result.boundary_mode == "boundary" else "کادر محدوده",
            tone="good" if result.boundary_mode == "boundary" else "warn",
            hint="نتایج به مرز واقعی منطقه محدود شده‌اند"
            if result.boundary_mode == "boundary"
            else "ممکن است مکان‌های خارج از منطقه هم آمده باشند",
            badge="دقیق" if result.boundary_mode == "boundary" else "تقریبی",
        ),
        ui.Card(
            "🏷️", "تأسیسات بدون نام", fa_digits(report.unnamed),
            tone="good" if unnamed_share < 0.15 else ("warn" if unnamed_share < 0.40 else "bad"),
            hint=f"{fa_digits(f'{unnamed_share * 100:.0f}')}٪ از کل موارد",
            badge="مطلوب" if unnamed_share < 0.15 else ("قابل توجه" if unnamed_share < 0.40 else "نیازمند بررسی"),
        ),
        ui.Card(
            "🔁", "احتمال تکرار", fa_digits(report.possible_duplicates),
            tone="good" if report.possible_duplicates == 0 else "warn",
            hint="موارد هم‌نام و نزدیک به هم (حذف نشده‌اند)",
            badge="بدون مورد" if report.possible_duplicates == 0 else "بررسی شود",
        ),
        ui.Card(
            "🚫", "کنار گذاشته‌شده", fa_digits(excluded),
            tone="info",
            hint="خارج از منطقه یا دارای مختصات نامعتبر",
            badge="اطلاعات",
        ),
    ]
)

# ---- Tabs: map & chart, table, data quality, guide -------------------------
tab_map, tab_table, tab_quality, tab_help = st.tabs(
    [
        ":material/map: نقشه و آمار دسته‌ها",
        ":material/table_chart: جدول تأسیسات",
        ":material/fact_check: کیفیت داده و جزئیات پردازش",
        ":material/help: راهنما",
    ]
)

with tab_map:
    map_col, chart_col = st.columns([3.4, 1.1], gap="medium")
    with map_col:
        token = f"result:{result.region.key}:{result.retrieved_at}:{','.join(result.category_keys)}"
        show_map(result.facilities, result.region, token, height=740)
    with chart_col:
        ui.category_bars(
            counts,
            title="تعداد تأسیسات در هر دسته",
            footnote="عدد صفر یعنی موردی در OSM ثبت نشده است، نه اینکه چنین تأسیساتی وجود ندارد.",
        )


# Table in a fragment: filtering reruns only the table, never the map.
@st.fragment
def facility_table(result: FacilityResult) -> None:
    frame = facilities_to_dataframe(result.facilities)
    view = pd.DataFrame(
        {
            "name": frame["name"].fillna("— بدون نام —"),
            "category": frame["category"].map(fa.category_label),
            "address": frame["address"],
            "operator": frame["operator"],
            "phone": frame["phone"],
            "website": frame["website"],
            "precision": frame["location_precision"].map(lambda v: fa.LOCATION_PRECISION_FA.get(v, v)),
            "flags": frame["quality_flags"].map(fa.translate_flags),
            "latitude": frame["latitude"],
            "longitude": frame["longitude"],
            "source_id": frame["source_id"],
            "osm_url": frame["osm_url"],
        }
    )
    label_to_key = {fa.category_label(k): k for k in result.category_keys}

    f1, f2 = st.columns([2, 1])
    search_text = f1.text_input(
        "جستجو در نام، نشانی، بهره‌بردار یا شناسهٔ OSM",
        key="table_search",
        placeholder="عبارت موردنظر را بنویسید…",
    )
    category_filter = f2.multiselect(
        "فیلتر دسته",
        options=list(label_to_key),
        key="table_categories",
        placeholder="همهٔ دسته‌ها",
    )
    filtered = view
    if search_text.strip():
        needle = search_text.strip()
        mask = pd.Series(False, index=filtered.index)
        for column in ("name", "address", "operator", "source_id", "category", "phone"):
            mask |= filtered[column].fillna("").astype(str).str.contains(needle, case=False, regex=False)
        filtered = filtered[mask]
    if category_filter:
        filtered = filtered[filtered["category"].isin(category_filter)]

    st.dataframe(
        filtered,
        hide_index=True,
        width="stretch",
        height=520,
        column_config={
            "name": st.column_config.TextColumn("نام"),
            "category": st.column_config.TextColumn("دسته"),
            "address": st.column_config.TextColumn("نشانی"),
            "operator": st.column_config.TextColumn("بهره‌بردار"),
            "phone": st.column_config.TextColumn("تلفن"),
            "website": st.column_config.LinkColumn("وب‌سایت"),
            "precision": st.column_config.TextColumn("دقت موقعیت"),
            "flags": st.column_config.TextColumn("کیفیت داده"),
            "latitude": st.column_config.NumberColumn("عرض جغرافیایی", format="%.6f"),
            "longitude": st.column_config.NumberColumn("طول جغرافیایی", format="%.6f"),
            "source_id": st.column_config.TextColumn("شناسه OSM"),
            "osm_url": st.column_config.LinkColumn("پیوند OSM", display_text="مشاهده"),
        },
    )
    st.caption(
        f"نمایش {fa_digits(len(filtered))} از {fa_digits(len(frame))} مورد "
        "(فیلتر جدول روی نقشه و فایل‌های خروجی اثری ندارد)."
    )


with tab_table:
    facility_table(result)

with tab_quality:
    if quality_warnings:
        ui.box("amber", quality_warnings, title="نکات کیفیت داده", icon="🔍")
    else:
        ui.box("green", "مورد قابل توجهی در کیفیت داده‌ها مشاهده نشد.", icon="✅")
    rows = "".join(
        f"<tr><td>{label}</td><td class='num'>{fa_digits(getattr(report, attr))}</td></tr>"
        for attr, label in fa.PROCESSING_STEPS_FA
    )
    st.markdown(
        "<table class='gc-table'><thead><tr><th>مرحلهٔ پردازش</th><th>تعداد رکورد</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )
    ui.box(
        "blue",
        "حذف موارد تکراری فقط تکرار یک عنصر OSM را حذف می‌کند. تأسیساتی که به چند شکل ثبت شده‌اند (مثلاً یک نقطه و "
        "یک محدودهٔ ساختمان) ممکن است بیش از یک بار دیده شوند و به همین دلیل علامت‌گذاری می‌شوند.",
        icon="ℹ️",
    )
    with st.expander("پرس‌وجوی ارسال‌شده به Overpass", icon=":material/code:"):
        st.code(result.query, language="text")

with tab_help:
    ui.box("green", fa.GUIDE_STEPS, title="مراحل کار با سامانه", icon="📌", ordered=True)
    ui.box(
        "blue",
        [
            "نقشه: با فهرست لایه‌ها (بالای نقشه) هر دسته را نمایش دهید یا پنهان کنید؛ با کلیک روی هر نشانگر، "
            "جزئیات تأسیسات نمایش داده می‌شود.",
            "نشانگرهای نزدیک به هم در بزرگ‌نمایی کم به‌صورت خوشه نمایش داده می‌شوند.",
            "برای محدوده‌ها و ساختمان‌ها، نشانگر روی مرکز تقریبی قرار می‌گیرد و لزوماً محل ورودی نیست.",
            "خروجی CSV برای صفحه‌گسترده، GeoJSON برای نرم‌افزارهای GIS و JSON برای پردازش‌های بعدی مناسب است.",
            "نتایج جستجو تا ۲۴ ساعت و نتایج تأسیسات تا ۶ ساعت ذخیره می‌شوند تا بار سرویس‌های عمومی کاهش یابد.",
        ],
        title="نکات کاربردی",
        icon="💡",
    )
    ui.box("blue", fa.STATUS_DISCLAIMER, title="اعتبار داده‌ها", icon="ℹ️")
