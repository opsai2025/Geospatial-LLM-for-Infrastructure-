import config
from services.facility_service import build_result
from services.http_client import (
    AllEndpointsFailedError,
    QueryTooLargeError,
    RateLimitError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from ui.i18n_fa import endpoint_line, result_warnings, service_error_message, translate_flag, translate_flags
from ui.persian import fa_digits, format_jalali_datetime, gregorian_to_jalali


def test_fa_digits():
    assert fa_digits(1234) == "۱٬۲۳۴"
    assert fa_digits(0) == "۰"
    assert fa_digits(2.5) == "۲٫۵"
    # strings: only digits change, punctuation is kept
    assert fa_digits("relation/62487.") == "relation/۶۲۴۸۷."


def test_gregorian_to_jalali():
    assert gregorian_to_jalali(2026, 10, 19) == (1405, 7, 27)
    assert gregorian_to_jalali(2024, 3, 20) == (1403, 1, 1)
    assert gregorian_to_jalali(2025, 3, 21) == (1404, 1, 1)
    assert gregorian_to_jalali(2023, 12, 31) == (1402, 10, 10)


def test_format_jalali_datetime_uses_tehran_time():
    text = format_jalali_datetime("2026-10-19T11:08:59+00:00")
    assert text == "۲۷ مهر ۱۴۰۵، ساعت ۱۴:۳۸ (وقت تهران)"
    assert format_jalali_datetime("not a date") == "not a date"


def test_every_category_has_persian_label_and_icons():
    for definition in config.CATEGORIES.values():
        assert definition.label_fa and definition.ui_icon.startswith(":material/") and definition.emoji


def test_flag_translation():
    assert translate_flag("missing_name") == "بدون نام"
    assert translate_flag("possible_duplicate:way/2") == "احتمال تکرار با way/2"
    assert translate_flags("missing_name;shelter_type_unspecified") == "بدون نام، نوع سرپناه نامشخص"
    assert translate_flags("") == ""


def test_error_messages_are_persian():
    assert "در دسترس نیست" in service_error_message(ServiceUnavailableError("x", service="Overpass API", status_code=502))
    assert "۵۰۲" in service_error_message(ServiceUnavailableError("x", service="Overpass API", status_code=502))
    assert "سقف تعداد درخواست" in service_error_message(RateLimitError("x", service="Nominatim", status_code=429))
    assert "کیلومتر مربع" in service_error_message(QueryTooLargeError("x"), area_km2=10 ** 6)


def test_all_endpoints_failed_message_is_persian():
    exc = AllEndpointsFailedError(
        "Overpass API",
        [
            ("https://a.test/api/interpreter", ServiceUnavailableError("x", status_code=502)),
            ("https://b.test/api/interpreter", ServiceTimeoutError("x")),
            ("https://c.test/api/interpreter", ServiceUnavailableError("x")),
        ],
    )
    text = service_error_message(exc)
    assert "هیچ‌یک از ۳ سرور" in text
    assert "a.test" in text and "b.test" in text and "c.test" in text
    assert "۵۰۲" in text and "پایان مهلت" in text and "عدم اتصال" in text


def test_endpoint_line_marks_fallback():
    assert config.OVERPASS_URL in endpoint_line(config.OVERPASS_URL)
    assert "جایگزین" not in endpoint_line(config.OVERPASS_URL)
    assert "جایگزین" in endpoint_line("https://fallback.test/api/interpreter")


def test_result_warnings(bbox_only_region):
    result = build_result(bbox_only_region, ["hospital"], [], retrieved_at="t", source_endpoint="e", query="q")
    important, quality = result_warnings(result)
    assert any("کادر محدوده" in w for w in important)
    assert any("ثبت نشده‌اند" in w for w in important)
    assert quality == []
