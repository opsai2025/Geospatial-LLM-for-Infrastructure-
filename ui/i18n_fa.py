"""Persian texts and translation helpers for the user interface.

Data and service layers stay in English (their output feeds later stages);
everything the end user reads is translated here.
"""

from __future__ import annotations

from urllib.parse import urlparse

import config
from models.region import Region
from services.facility_service import FacilityResult
from services.http_client import (
    AllEndpointsFailedError,
    QueryTooLargeError,
    RateLimitError,
    ServiceError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    UnexpectedResponseError,
)
from ui.persian import fa_digits

APP_TITLE = "سامانه پایش تأسیسات حیاتی شهری"
APP_SUBTITLE = "شناسایی تأسیسات امدادی و خدمات عمومی از OpenStreetMap برای مدیریت بحران"
BRAND_TITLE = "سامانه پایش تأسیسات حیاتی"
BRAND_SUBTITLE = "عامل مدیریت بحران · مرحله ۱"

STATUS_DISCLAIMER = (
    "تأسیسات نمایش‌داده‌شده صرفاً در OpenStreetMap ثبت شده‌اند. نمایش آن‌ها روی نقشه به معنای باز بودن، "
    "فعال بودن یا در دسترس بودن آن‌ها نیست. پوشش داده‌های OSM کامل نیست و در مناطق مختلف متفاوت است؛ "
    "بنابراین ممکن است برخی تأسیسات موجود در نقشه ثبت نشده باشند."
)

GUIDE_STEPS = [
    "در نوار کناری، نام شهر، شهرستان یا منطقه را وارد کرده و «جستجو» را بزنید.",
    "اگر چند مکان مشابه یافت شد، مکان درست را از فهرست انتخاب کنید.",
    "دسته‌های تأسیسات موردنظر را انتخاب کنید (به‌طور پیش‌فرض همه انتخاب شده‌اند).",
    "روی «بارگذاری تأسیسات» کلیک کنید تا داده‌ها از OpenStreetMap دریافت شوند.",
    "نتایج را در نقشه، نمودار و جدول بررسی کرده و در قالب CSV، GeoJSON یا JSON دریافت کنید.",
]

LOCATION_PRECISION_FA = {
    "osm_node": "نقطهٔ ثبت‌شده",
    "osm_way_center": "مرکز تقریبی محدوده",
    "osm_relation_center": "مرکز تقریبی مجموعه",
}

PLACE_TYPE_FA = {
    "administrative": "مرز اداری",
    "city": "شهر",
    "town": "شهر کوچک",
    "village": "روستا",
    "hamlet": "آبادی",
    "suburb": "محله",
    "neighbourhood": "محله",
    "quarter": "ناحیه",
    "borough": "منطقه",
    "district": "بخش",
    "county": "شهرستان",
    "municipality": "شهرداری",
    "state": "استان",
    "province": "استان",
    "region": "منطقه",
    "country": "کشور",
    "island": "جزیره",
    "postcode": "کد پستی",
}

SERVICE_NAME_FA = {
    "Nominatim": "سرویس جستجوی مکان (Nominatim)",
    "Overpass API": "سرویس داده‌های تأسیسات (Overpass)",
}


def category_label(key: str) -> str:
    definition = config.CATEGORIES.get(key)
    return (definition.label_fa or definition.label) if definition else key


def region_option_label(region: Region) -> str:
    kind = PLACE_TYPE_FA.get(region.place_type or "", region.place_type or "مکان")
    boundary = "دارای مرز" if region.has_boundary else "بدون مرز"
    return f"{region.display_name}  ({kind} · {boundary})"


def translate_flag(flag: str) -> str:
    if flag == "missing_name":
        return "بدون نام"
    if flag.startswith("possible_duplicate:"):
        return f"احتمال تکرار با {flag.split(':', 1)[1]}"
    if flag == "shelter_type_unspecified":
        return "نوع سرپناه نامشخص"
    if flag == "likely_not_emergency_shelter":
        return "احتمالاً سرپناه اضطراری نیست"
    if flag.startswith("shelter_type:"):
        return f"نوع سرپناه: {flag.split(':', 1)[1]}"
    return flag


def translate_flags(flags: str) -> str:
    """Translate a ';'-joined flag string from the export table."""
    return "، ".join(translate_flag(f) for f in flags.split(";") if f) if flags else ""


def ltr(text: str) -> str:
    """Isolate a left-to-right fragment (URL, host name) inside Persian text."""
    return f"⁨{text}⁩"


def _host(url: str) -> str:
    return urlparse(url).netloc or url


def endpoint_line(url: str) -> str:
    """Status line naming the Overpass server that actually served the data."""
    line = f"سرور پاسخ‌دهنده: {ltr(url)}"
    if url != config.OVERPASS_URL:
        line += " (سرور جایگزین؛ سرور اصلی در دسترس نبود)"
    return line


def _failure_reason(exc: ServiceError) -> str:
    if exc.status_code:
        return f"کد HTTP {fa_digits(str(exc.status_code))}"
    if isinstance(exc, ServiceTimeoutError):
        return "پایان مهلت پاسخ‌گویی"
    return "عدم اتصال"


def service_error_message(exc: ServiceError, *, area_km2: float | None = None) -> str:
    service = SERVICE_NAME_FA.get(exc.service, exc.service or "سرویس")
    code = f" (کد HTTP {fa_digits(str(exc.status_code))})" if exc.status_code else ""
    if isinstance(exc, AllEndpointsFailedError):
        tried = "، ".join(f"{ltr(_host(url))} ({_failure_reason(e)})" for url, e in exc.failures)
        return (
            f"{service}: هیچ‌یک از {fa_digits(len(exc.failures))} سرور پیکربندی‌شده پاسخ نداد. "
            f"سرورهای آزموده‌شده: {tried}. لطفاً کمی بعد دوباره تلاش کنید."
        )
    if isinstance(exc, QueryTooLargeError):
        if area_km2 is not None and area_km2 > config.MAX_QUERY_AREA_KM2:
            return (
                f"محدودهٔ انتخاب‌شده حدود {fa_digits(round(area_km2))} کیلومتر مربع است و از سقف "
                f"{fa_digits(round(config.MAX_QUERY_AREA_KM2))} کیلومتر مربع برای یک درخواست بزرگ‌تر است. "
                "لطفاً یک شهر یا بخش کوچک‌تر را انتخاب کنید."
            )
        return (
            f"{service}: حجم این درخواست برای سرور بیش از حد بزرگ است. محدودهٔ کوچک‌تر یا دسته‌های کمتری "
            "انتخاب کنید."
        )
    if isinstance(exc, ServiceTimeoutError):
        return (
            f"{service}: مهلت پاسخ‌گویی به پایان رسید{code}. ممکن است سرور شلوغ یا محدوده بزرگ باشد؛ "
            "کمی بعد دوباره تلاش کنید یا محدودهٔ کوچک‌تری انتخاب کنید."
        )
    if isinstance(exc, RateLimitError):
        return f"{service}: سقف تعداد درخواست‌ها پر شده است{code}. لطفاً یک دقیقه صبر کرده و دوباره تلاش کنید."
    if isinstance(exc, ServiceUnavailableError):
        return f"{service}: سرویس موقتاً در دسترس نیست{code}. لطفاً کمی بعد دوباره تلاش کنید."
    if isinstance(exc, UnexpectedResponseError):
        return f"{service}: پاسخ دریافت‌شده قابل پردازش نبود{code}. ممکن است سرویس در حال به‌روزرسانی باشد."
    return f"{service}: خطا در انجام درخواست{code}."


def result_warnings(result: FacilityResult) -> tuple[list[str], list[str]]:
    """Return (important, quality) warnings in Persian."""
    r = result.report
    important: list[str] = []
    quality: list[str] = []
    if result.boundary_mode == "bbox":
        important.append(
            "مرز اداری این منطقه در دسترس نبود؛ نتایج فقط به کادر محدوده (Bounding Box) محدود شده و ممکن است "
            "شامل مکان‌هایی خارج از منطقهٔ واقعی باشد."
        )
    if r.final_count == 0:
        important.append(
            "هیچ تأسیساتی از دسته‌های انتخاب‌شده یافت نشد. این یعنی در OpenStreetMap ثبت نشده‌اند، نه اینکه "
            "وجود ندارند."
        )
    if r.unnamed:
        quality.append(f"{fa_digits(r.unnamed)} مورد در OSM نام ندارند (با برچسب «بدون نام» علامت‌گذاری شده و حذف نشده‌اند).")
    if r.possible_duplicates:
        quality.append(
            f"{fa_digits(r.possible_duplicates)} مورد هم‌نام و هم‌دسته با موردی نزدیک هستند و ممکن است یک تأسیسات "
            "واقعی باشند (علامت‌گذاری شده، حذف نشده‌اند)."
        )
    if r.missing_coordinates or r.invalid_coordinates:
        quality.append(
            f"{fa_digits(r.missing_coordinates + r.invalid_coordinates)} مورد به دلیل مختصات ناقص یا نامعتبر "
            "کنار گذاشته شدند."
        )
    if r.outside_region:
        quality.append(f"{fa_digits(r.outside_region)} مورد خارج از محدودهٔ منطقه بودند و کنار گذاشته شدند.")
    if "shelter" in result.category_keys and any(f.category == "shelter" for f in result.facilities):
        quality.append(
            "برچسب amenity=shelter در OSM علاوه بر سرپناه اضطراری، سایبان ایستگاه اتوبوس و سرپناه تفریحی را هم "
            "شامل می‌شود؛ موارد غیراضطراری آشکار با برچسب «احتمالاً سرپناه اضطراری نیست» مشخص شده‌اند."
        )
    return important, quality


PROCESSING_STEPS_FA = [
    ("total_elements", "عناصر دریافتی از Overpass"),
    ("unclassified", "خارج از دسته‌های انتخاب‌شده"),
    ("unsupported", "عناصر پشتیبانی‌نشده"),
    ("missing_coordinates", "فاقد مختصات (حذف‌شده)"),
    ("invalid_coordinates", "مختصات نامعتبر (حذف‌شده)"),
    ("duplicates_removed", "عناصر تکراری OSM (حذف‌شده)"),
    ("outside_region", "خارج از منطقه (حذف‌شده)"),
    ("possible_duplicates", "احتمال تکرار (نگه‌داشته‌شده)"),
    ("unnamed", "بدون نام (نگه‌داشته‌شده)"),
    ("final_count", "تعداد نهایی تأسیسات"),
]
