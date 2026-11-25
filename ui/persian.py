"""Persian number and date formatting (no external dependencies)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Iran has used a fixed UTC+03:30 offset (no daylight saving) since 2022.
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_FA_NUMBER = str.maketrans("0123456789,.", "۰۱۲۳۴۵۶۷۸۹٬٫")

JALALI_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)


def fa_digits(value) -> str:
    """Render with Persian digits.

    Numbers also get Persian thousands/decimal separators (1234 -> ۱٬۲۳۴).
    In strings only the digits are replaced, so punctuation is untouched.
    """
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}".translate(_FA_NUMBER)
    if isinstance(value, float):
        text = f"{int(value):,}" if value.is_integer() else f"{value:,.1f}"
        return text.translate(_FA_NUMBER)
    return str(value).translate(_FA_DIGITS)


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Convert a Gregorian date to the Solar Hijri (Jalali) calendar."""
    g_d_m = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def format_jalali_datetime(iso_timestamp: str) -> str:
    """'2026-10-19T11:08:59+00:00' -> '۲۷ مهر ۱۴۰۵، ساعت ۱۴:۳۸ (وقت تهران)'."""
    try:
        moment = datetime.fromisoformat(iso_timestamp)
    except (TypeError, ValueError):
        return iso_timestamp or "—"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(TEHRAN_TZ)
    jy, jm, jd = gregorian_to_jalali(local.year, local.month, local.day)
    return fa_digits(f"{jd} {JALALI_MONTHS[jm - 1]} {jy}، ساعت {local:%H:%M} (وقت تهران)")
