"""Central configuration for the GeoCrisis Agent (Stage 1).

Every external endpoint and usage-policy setting can be overridden with an
environment variable so the app can be pointed at self-hosted Nominatim /
Overpass / tile servers without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


APP_NAME = "GeoCrisis Agent"
APP_VERSION = "0.1.0"

# --------------------------------------------------------------------------
# Identification (required by the Nominatim and Overpass usage policies)
# --------------------------------------------------------------------------
# Set GEOCRISIS_CONTACT to an e-mail address or project URL so service
# operators can reach you if your traffic causes problems.
CONTACT = _env_str("GEOCRISIS_CONTACT", "")
USER_AGENT = _env_str(
    "GEOCRISIS_USER_AGENT",
    f"GeoCrisisAgent/{APP_VERSION} (stage-1 facility mapping prototype"
    + (f"; contact: {CONTACT}" if CONTACT else "")
    + ")",
)

# --------------------------------------------------------------------------
# Nominatim (region search / geocoding)
# --------------------------------------------------------------------------
NOMINATIM_URL = _env_str("GEOCRISIS_NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
NOMINATIM_TIMEOUT_S = _env_float("GEOCRISIS_NOMINATIM_TIMEOUT", 20.0)
NOMINATIM_RESULT_LIMIT = _env_int("GEOCRISIS_NOMINATIM_LIMIT", 8)
# Public Nominatim allows an absolute maximum of 1 request per second.
NOMINATIM_MIN_INTERVAL_S = _env_float("GEOCRISIS_NOMINATIM_MIN_INTERVAL", 1.1)
# Simplification tolerance (degrees) for returned boundary polygons.
NOMINATIM_POLYGON_THRESHOLD = _env_float("GEOCRISIS_NOMINATIM_POLYGON_THRESHOLD", 0.0001)
NOMINATIM_LANGUAGE = _env_str("GEOCRISIS_NOMINATIM_LANGUAGE", "fa,en")

# --------------------------------------------------------------------------
# Overpass (facility queries)
# --------------------------------------------------------------------------
DEFAULT_OVERPASS_URLS: tuple[str, ...] = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)


def _overpass_urls() -> tuple[str, ...]:
    """Endpoints tried in order; later ones are used only when earlier ones are down.

    GEOCRISIS_OVERPASS_URLS (comma-separated) sets the whole list;
    GEOCRISIS_OVERPASS_URL alone pins a single endpoint without fallback.
    """
    urls = [u.strip() for u in os.environ.get("GEOCRISIS_OVERPASS_URLS", "").split(",") if u.strip()]
    if urls:
        return tuple(dict.fromkeys(urls))
    single = _env_str("GEOCRISIS_OVERPASS_URL", "")
    return (single,) if single else DEFAULT_OVERPASS_URLS


OVERPASS_URLS = _overpass_urls()
# Primary endpoint (first in the list).
OVERPASS_URL = OVERPASS_URLS[0]
# Server-side query timeout written into the Overpass QL header.
OVERPASS_QUERY_TIMEOUT_S = _env_int("GEOCRISIS_OVERPASS_QUERY_TIMEOUT", 90)
# Client-side HTTP timeout; slightly longer than the server-side timeout.
OVERPASS_HTTP_TIMEOUT_S = _env_float("GEOCRISIS_OVERPASS_HTTP_TIMEOUT", OVERPASS_QUERY_TIMEOUT_S + 20)
# Bounding boxes larger than this are refused before any request is sent.
MAX_QUERY_AREA_KM2 = _env_float("GEOCRISIS_MAX_QUERY_AREA_KM2", 25_000.0)

# --------------------------------------------------------------------------
# HTTP behaviour shared by all services
# --------------------------------------------------------------------------
# Number of *additional* attempts per endpoint after a 429/502/503/504 response.
# Kept small on purpose: the app never retries without a limit. With several
# Overpass endpoints one query sends at most
# len(OVERPASS_URLS) * (1 + HTTP_MAX_RETRIES) requests.
HTTP_MAX_RETRIES = _env_int("GEOCRISIS_HTTP_MAX_RETRIES", 1)
HTTP_MAX_BACKOFF_S = _env_float("GEOCRISIS_HTTP_MAX_BACKOFF", 10.0)

# --------------------------------------------------------------------------
# Caching (Streamlit st.cache_data TTLs)
# --------------------------------------------------------------------------
GEOCODE_CACHE_TTL_S = _env_int("GEOCRISIS_GEOCODE_CACHE_TTL", 24 * 3600)
FACILITY_CACHE_TTL_S = _env_int("GEOCRISIS_FACILITY_CACHE_TTL", 6 * 3600)

# --------------------------------------------------------------------------
# Map tiles
# --------------------------------------------------------------------------
# The default is the OSM Foundation's standard tile server, which is fine for
# light interactive use under its tile usage policy
# (https://operations.osmfoundation.org/policies/tiles/). For heavier use,
# point these variables at a commercial or self-hosted tile provider.
TILE_URL = _env_str("GEOCRISIS_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
TILE_ATTRIBUTION = _env_str(
    "GEOCRISIS_TILE_ATTRIBUTION",
    '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">'
    "OpenStreetMap</a> contributors",
)
TILE_NAME = _env_str("GEOCRISIS_TILE_NAME", "OpenStreetMap")
TILE_MAX_ZOOM = _env_int("GEOCRISIS_TILE_MAX_ZOOM", 19)

# Clustering is applied to a category layer once it has this many markers.
CLUSTER_THRESHOLD = _env_int("GEOCRISIS_CLUSTER_THRESHOLD", 30)

# --------------------------------------------------------------------------
# Data quality
# --------------------------------------------------------------------------
# Same-category facilities with the same name closer than this are flagged
# as possible duplicates (they are never removed automatically).
POSSIBLE_DUPLICATE_DISTANCE_M = _env_float("GEOCRISIS_POSSIBLE_DUPLICATE_DISTANCE_M", 100.0)

DATA_SOURCE = "OpenStreetMap"
DATA_ATTRIBUTION = "© OpenStreetMap contributors"
DATA_LICENSE = "Open Database License (ODbL) 1.0"
DATA_LICENSE_URL = "https://www.openstreetmap.org/copyright"

STATUS_DISCLAIMER = (
    "Facilities are shown because they are mapped in OpenStreetMap. Their presence on "
    "this map does not mean they are open, operational, staffed, or accessible. OSM "
    "coverage is incomplete and varies by area, so missing facilities may still exist."
)


# --------------------------------------------------------------------------
# Facility categories
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class CategoryDefinition:
    key: str
    label: str
    osm_tags: tuple[tuple[str, str], ...]
    marker_color: str  # one of folium.Icon's supported colours
    icon: str  # Font Awesome icon name (map markers)
    hex_color: str  # used for legends / tables
    label_fa: str = ""  # Persian display label
    ui_icon: str = ""  # Streamlit Material icon, e.g. ":material/local_hospital:"
    emoji: str = ""  # icon for custom HTML elements


CATEGORIES: dict[str, CategoryDefinition] = {
    c.key: c
    for c in (
        CategoryDefinition(
            "hospital", "Hospitals", (("amenity", "hospital"),), "red", "plus", "#d63e2a",
            "بیمارستان‌ها", ":material/local_hospital:", "🏥",
        ),
        CategoryDefinition(
            "clinic", "Clinics and medical centres", (("amenity", "clinic"), ("amenity", "doctors")),
            "lightred", "stethoscope", "#ff8e7f",
            "درمانگاه‌ها و مراکز پزشکی", ":material/medical_services:", "🩺",
        ),
        CategoryDefinition(
            "police", "Police stations", (("amenity", "police"),), "darkblue", "shield", "#0067a3",
            "کلانتری‌ها و مراکز پلیس", ":material/local_police:", "👮",
        ),
        CategoryDefinition(
            "fire_station", "Fire stations", (("amenity", "fire_station"),), "darkred", "fire", "#a23336",
            "ایستگاه‌های آتش‌نشانی", ":material/local_fire_department:", "🚒",
        ),
        CategoryDefinition(
            "government", "Government offices", (("office", "government"),), "purple", "building", "#d252b9",
            "ادارات دولتی", ":material/account_balance:", "🏛️",
        ),
        CategoryDefinition(
            "townhall", "Town halls and municipal offices", (("amenity", "townhall"),), "cadetblue",
            "university", "#436978",
            "شهرداری‌ها و دفاتر شهری", ":material/location_city:", "🏢",
        ),
        CategoryDefinition(
            "courthouse", "Courthouses", (("amenity", "courthouse"),), "darkpurple", "gavel", "#5b396b",
            "دادگاه‌ها و مراجع قضایی", ":material/gavel:", "⚖️",
        ),
        CategoryDefinition(
            "pharmacy", "Pharmacies", (("amenity", "pharmacy"),), "green", "medkit", "#72b026",
            "داروخانه‌ها", ":material/local_pharmacy:", "💊",
        ),
        CategoryDefinition(
            "shelter", "Emergency shelters", (("amenity", "shelter"),), "orange", "home", "#f69730",
            "پناهگاه‌ها و سرپناه‌ها", ":material/night_shelter:", "⛺",
        ),
        CategoryDefinition(
            "fuel", "Fuel stations", (("amenity", "fuel"),), "gray", "car", "#575757",
            "جایگاه‌های سوخت", ":material/local_gas_station:", "⛽",
        ),
    )
}

# When an element carries several supported tags (e.g. amenity=townhall plus
# office=government) the first key in this list decides its category.
TAG_KEY_PRIORITY: tuple[str, ...] = ("amenity", "office")

# amenity=shelter covers many shelter kinds in OSM. These shelter_type values
# are clearly not emergency shelters and are flagged (not removed).
NON_EMERGENCY_SHELTER_TYPES: frozenset[str] = frozenset(
    {"public_transport", "picnic_shelter", "gazebo", "lean_to", "rock_shelter", "sun_shelter", "field_shelter"}
)
