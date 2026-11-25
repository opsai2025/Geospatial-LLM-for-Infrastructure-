"""Folium map of facilities: one toggleable layer per category."""

from __future__ import annotations

import html
import json
from collections import defaultdict
from collections.abc import Sequence

import folium
from folium.plugins import MarkerCluster
from shapely.geometry import mapping

import config
from models.facility import Facility
from models.region import Region
from ui.i18n_fa import translate_flag
from ui.persian import fa_digits

PRECISION_TEXT = {
    "osm_node": "نقطهٔ ثبت‌شده در نقشه",
    "osm_way_center": "تقریبی (مرکز محدودهٔ ثبت‌شده)",
    "osm_relation_center": "تقریبی (مرکز مجموعهٔ ثبت‌شده)",
}

FONT_STACK = "BNazanin, 'B Nazanin', Vazirmatn, Tahoma, sans-serif"

# Persian font and right-to-left text for popups, tooltips and the layer list.
# The tiles themselves are the unchanged default OpenStreetMap map.
MAP_CSS = f"""
<style>
@font-face {{ font-family: 'BNazanin'; font-weight: 400;
  src: local('B Nazanin'), local('BNazanin'), url('app/static/fonts/BNazanin.ttf') format('truetype'); }}
@font-face {{ font-family: 'BNazanin'; font-weight: 700;
  src: local('B Nazanin Bold'), local('BNazanin-Bold'), url('app/static/fonts/BNazanin-Bold.ttf') format('truetype'); }}
.leaflet-popup-content, .leaflet-tooltip, .leaflet-control-layers {{ font-family: {FONT_STACK}; }}
.leaflet-popup-content {{ direction: rtl; text-align: right; }}
.leaflet-tooltip {{ direction: rtl; font-size: 14px; }}
.leaflet-control-layers {{ direction: rtl; text-align: right; font-size: 15px; line-height: 1.7; }}
.leaflet-control-layers label {{ margin: 2px 0; }}
.gc-fullscreen a {{ font-size: 18px; line-height: 30px; cursor: pointer; user-select: none; }}
.gc-fullscreen.gc-active a {{ background: #0f172a; color: #ffffff; font-size: 16px; }}
.gc-fullscreen-hint {{
  position: absolute; top: 12px; left: 50%; transform: translateX(-50%); z-index: 1000;
  background: rgba(15, 23, 42, .85); color: #fff; padding: 4px 14px; border-radius: 8px;
  font-family: {FONT_STACK}; font-size: 15px; direction: rtl; pointer-events: none;
  opacity: 0; transition: opacity .3s;
}}
.gc-fullscreen-hint.gc-show {{ opacity: 1; }}
</style>
"""


def _row(label: str, value: str | None, *, is_html: bool = False) -> str:
    if not value:
        return ""
    shown = value if is_html else html.escape(value)
    return (
        f"<tr><th style='text-align:right;padding-left:8px;vertical-align:top;white-space:nowrap'>{label}</th>"
        f"<td>{shown}</td></tr>"
    )


def _safe_link(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return html.escape(url)
    escaped = html.escape(url, quote=True)
    return f"<a href='{escaped}' target='_blank' rel='noopener noreferrer' dir='ltr'>{escaped}</a>"


def facility_popup_html(facility: Facility) -> str:
    name = html.escape(facility.name) if facility.name else "<i>بدون نام (نامی در OSM ثبت نشده)</i>"
    definition = config.CATEGORIES.get(facility.category)
    category = (definition.label_fa or definition.label) if definition else facility.category_label
    rows = "".join(
        [
            _row("دسته", category),
            _row("نشانی", facility.address),
            _row("بهره‌بردار", facility.operator),
            _row("تلفن", f"<span dir='ltr'>{html.escape(facility.phone)}</span>" if facility.phone else None,
                 is_html=True),
            _row("وب‌سایت", _safe_link(facility.website), is_html=True),
            _row("موقعیت", PRECISION_TEXT.get(facility.location_precision, facility.location_precision)),
            _row("کیفیت داده", "، ".join(translate_flag(f) for f in facility.quality_flags) or None),
            _row(
                "شناسه OSM",
                f"<a href='{facility.osm_url}' target='_blank' rel='noopener noreferrer' dir='ltr'>"
                f"{facility.source_id}</a>",
                is_html=True,
            ),
        ]
    )
    return (
        f"<div dir='rtl' style='font-family:{FONT_STACK};font-size:15px;line-height:1.8;min-width:230px'>"
        f"<b style='font-size:17px'>{name}</b>"
        f"<table style='margin-top:4px'>{rows}</table>"
        "<div style='margin-top:6px;color:#555;font-size:13px'>"
        "ثبت‌شده در OpenStreetMap؛ وضعیت فعالیت تأیید نشده است."
        "</div></div>"
    )


def _add_region_outline(fmap: folium.Map, region: Region) -> None:
    if region.has_boundary:
        folium.GeoJson(
            mapping(region.boundary),
            name="مرز منطقه",
            style_function=lambda _: {"color": "#3366cc", "weight": 2, "fill": True, "fillOpacity": 0.04},
            tooltip=html.escape(region.display_name),
        ).add_to(fmap)
    else:
        b = region.bbox
        folium.Rectangle(
            bounds=[[b.south, b.west], [b.north, b.east]],
            color="#cc6633",
            weight=2,
            dash_array="6",
            fill=False,
            tooltip="کادر محدوده (مرز اداری در دسترس نیست)",
            name="کادر محدوده",
        ).add_to(fmap)


# Leaflet measures its container once. If the map is created while hidden
# (e.g. inside an inactive tab) it stays 0x0 and draws nothing. This script
# re-measures whenever the container size changes and, the first time the
# map becomes visible, re-fits it to the region. It runs on window load,
# after folium's own script has created the map.
RESIZE_JS = """
window.addEventListener("load", function () {
  var map = %(map)s;
  var bounds = %(bounds)s;
  var el = map.getContainer();
  var laidOut = el.clientWidth > 0 && el.clientHeight > 0;
  function refresh() {
    var w = el.clientWidth, h = el.clientHeight;
    if (!w || !h) { return; }
    var size = map.getSize();
    if (size.x === w && size.y === h && laidOut) { return; }
    map.invalidateSize(false);
    if (!laidOut && bounds) { map.fitBounds(bounds); }
    laidOut = true;
  }
  if (window.ResizeObserver) { new ResizeObserver(refresh).observe(el); }
  window.addEventListener("resize", refresh);
  document.addEventListener("visibilitychange", refresh);
  setTimeout(refresh, 250);
});
"""


def _add_resize_guard(fmap: folium.Map, bounds: list[list[float]] | None) -> None:
    js = RESIZE_JS % {"map": fmap.get_name(), "bounds": json.dumps(bounds)}
    fmap.get_root().script.add_child(folium.Element(js))


# Full-screen toggle with no extra plugin to download. It uses the browser
# Fullscreen API; where that is refused or never answers (some embedded
# browsers), it falls back to stretching the map's iframe over the whole
# window. The same button or Esc leaves either mode, and a short hint says
# so. If neither mode is possible the button is not shown. The resize guard
# above re-measures the map whenever its size changes.
FULLSCREEN_JS = """
window.addEventListener("load", function () {
  var map = %(map)s;
  var el = map.getContainer();
  var doc = document;
  var frame = null;
  try { frame = window.frameElement; } catch (e) { frame = null; }
  var nativeOk = !!((doc.fullscreenEnabled || doc.webkitFullscreenEnabled) &&
                    (el.requestFullscreen || el.webkitRequestFullscreen));
  if (!nativeOk && !frame) { return; }
  var ENTER = "تمام‌صفحه", EXIT = "خروج از تمام‌صفحه (Esc)";
  var expanded = false, savedStyle = null, pending = null, hintTimer = null, control;
  function nativeOn() { return (doc.fullscreenElement || doc.webkitFullscreenElement) === el; }
  function isOn() { return nativeOn() || expanded; }
  var hint = L.DomUtil.create("div", "gc-fullscreen-hint", el);
  hint.textContent = "برای خروج از تمام‌صفحه، Esc یا دکمهٔ ✕ را بزنید";

  function sync() {
    var on = isOn();
    control._a.textContent = on ? "✕" : "⛶";
    control._a.title = on ? EXIT : ENTER;
    control._a.setAttribute("aria-label", control._a.title);
    L.DomUtil[on ? "addClass" : "removeClass"](control._box, "gc-active");
    clearTimeout(hintTimer);
    L.DomUtil[on ? "addClass" : "removeClass"](hint, "gc-show");
    if (on) { hintTimer = setTimeout(function () { L.DomUtil.removeClass(hint, "gc-show"); }, 3500); }
    setTimeout(function () { map.invalidateSize(false); }, 100);
  }
  function setExpanded(on) {
    if (!frame || expanded === on) { return; }
    try {
      if (on) {
        savedStyle = frame.getAttribute("style");
        frame.style.cssText = (savedStyle || "") + ";position:fixed;top:0;left:0;width:100vw;height:100vh;" +
          "max-width:none;max-height:none;margin:0;border:0;border-radius:0;z-index:2147483000;background:#fff;";
      } else if (savedStyle === null) {
        frame.removeAttribute("style");
      } else {
        frame.setAttribute("style", savedStyle);
      }
      expanded = on;
    } catch (e) { expanded = false; }
    sync();
  }
  function enter() {
    if (!nativeOk) { setExpanded(true); return; }
    try {
      var p = (el.requestFullscreen || el.webkitRequestFullscreen).call(el);
      if (p && p.catch) { p.catch(function () { setExpanded(true); }); }
    } catch (e) { setExpanded(true); return; }
    clearTimeout(pending);
    pending = setTimeout(function () { if (!nativeOn()) { setExpanded(true); } }, 1200);
  }
  function exit() {
    clearTimeout(pending);
    if (nativeOn()) {
      try { (doc.exitFullscreen || doc.webkitExitFullscreen).call(doc); } catch (e) {}
    }
    setExpanded(false);
  }

  var Control = L.Control.extend({
    options: { position: "topleft" },
    onAdd: function () {
      var box = L.DomUtil.create("div", "leaflet-bar leaflet-control gc-fullscreen");
      var a = L.DomUtil.create("a", "", box);
      a.href = "#"; a.setAttribute("role", "button");
      a.title = ENTER; a.setAttribute("aria-label", ENTER); a.textContent = "⛶";
      L.DomEvent.disableClickPropagation(box);
      L.DomEvent.on(a, "click", function (e) {
        L.DomEvent.preventDefault(e);
        if (isOn()) { exit(); } else { enter(); }
      });
      this._box = box; this._a = a;
      return box;
    }
  });
  control = new Control().addTo(map);

  function onFullscreenChange() {
    if (nativeOn()) { clearTimeout(pending); setExpanded(false); }
    sync();
  }
  doc.addEventListener("fullscreenchange", onFullscreenChange);
  doc.addEventListener("webkitfullscreenchange", onFullscreenChange);
  // Esc already leaves native full screen; this handles the window-filling fallback.
  function onKey(e) { if ((e.key === "Escape" || e.key === "Esc") && expanded) { exit(); } }
  doc.addEventListener("keydown", onKey);
  try { if (frame) { frame.ownerDocument.addEventListener("keydown", onKey); } } catch (e) {}
});
"""


def _add_fullscreen_control(fmap: folium.Map) -> None:
    fmap.get_root().script.add_child(folium.Element(FULLSCREEN_JS % {"map": fmap.get_name()}))


def build_facility_map(
    facilities: Sequence[Facility],
    region: Region | None = None,
    *,
    tile_url: str = config.TILE_URL,
    tile_attribution: str = config.TILE_ATTRIBUTION,
    tile_name: str = config.TILE_NAME,
    cluster_threshold: int = config.CLUSTER_THRESHOLD,
) -> folium.Map:
    """Create a map with one layer per category and a layer control."""
    if region is not None:
        center = [region.latitude, region.longitude]
    elif facilities:
        center = [
            sum(f.latitude for f in facilities) / len(facilities),
            sum(f.longitude for f in facilities) / len(facilities),
        ]
    else:
        center = [20.0, 0.0]

    fmap = folium.Map(location=center, zoom_start=12 if region else 2, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles=tile_url,
        attr=tile_attribution,
        name=tile_name,
        max_zoom=config.TILE_MAX_ZOOM,
        control=False,
    ).add_to(fmap)
    fmap.get_root().header.add_child(folium.Element(MAP_CSS))

    bounds = None
    if region is not None:
        _add_region_outline(fmap, region)
        b = region.bbox
        bounds = [[b.south, b.west], [b.north, b.east]]
        fmap.fit_bounds(bounds)

    by_category: dict[str, list[Facility]] = defaultdict(list)
    for facility in facilities:
        by_category[facility.category].append(facility)

    for key, definition in config.CATEGORIES.items():
        members = by_category.get(key)
        if not members:
            continue
        swatch = f"<span style='color:{definition.hex_color}'>&#9679;</span>"
        label = definition.label_fa or definition.label
        layer = folium.FeatureGroup(name=f"{swatch} {label} ({fa_digits(len(members))})", show=True)
        target = MarkerCluster(disableClusteringAtZoom=17).add_to(layer) if len(members) >= cluster_threshold else layer
        for facility in members:
            folium.Marker(
                location=[facility.latitude, facility.longitude],
                popup=folium.Popup(facility_popup_html(facility), max_width=320),
                tooltip=html.escape(facility.name or f"{label} (بدون نام)"),
                icon=folium.Icon(color=definition.marker_color, icon=definition.icon, prefix="fa"),
            ).add_to(target)
        layer.add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)
    _add_resize_guard(fmap, bounds)
    _add_fullscreen_control(fmap)
    return fmap


def render_map_html(facilities: Sequence[Facility], region: Region | None = None, **kwargs) -> str:
    """Build the map and return it as a self-contained HTML document.

    Embedding this static HTML is more robust than a live widget: the page is
    identical on every rerun, so the browser keeps the loaded map as it is.
    """
    return build_facility_map(facilities, region, **kwargs).get_root().render()
