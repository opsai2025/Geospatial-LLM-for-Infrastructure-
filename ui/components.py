"""Small HTML building blocks (header, help boxes, status cards, bar list)."""

from __future__ import annotations

import html
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import streamlit as st

import config
from ui.i18n_fa import category_label
from ui.persian import fa_digits

TONE_BADGE = {"good": "مطلوب", "warn": "نیازمند توجه", "bad": "ناقص", "info": "اطلاعات"}


def _md(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def header(title: str, subtitle: str, icon: str = "🛰️") -> None:
    _md(
        f"<div class='gc-header'><div class='gc-header-icon'>{icon}</div><div class='gc-header-text'>"
        f"<div class='gc-header-title'>{html.escape(title)}</div>"
        f"<div class='gc-header-sub'>{html.escape(subtitle)}</div></div></div>"
    )


def brand(title: str, subtitle: str, icon: str = "🛰️") -> None:
    _md(
        f"<div class='gc-brand'><div class='gc-brand-icon'>{icon}</div><div>"
        f"<div class='gc-brand-title'>{html.escape(title)}</div>"
        f"<div class='gc-brand-sub'>{html.escape(subtitle)}</div></div></div>"
    )


def side_title(icon: str, text: str) -> None:
    _md(f"<div class='gc-side-title'><span>{icon}</span><span>{html.escape(text)}</span></div>")


def side_note(text: str) -> None:
    _md(f"<div class='gc-side-note'>{html.escape(text)}</div>")


def side_region(text: str) -> None:
    _md(f"<div class='gc-side-region'>📍 {html.escape(text)}</div>")


def section(icon: str, text: str, sub: str | None = None) -> None:
    small = f"<small>{html.escape(sub)}</small>" if sub else ""
    _md(f"<div class='gc-section'><span>{icon}</span><span>{html.escape(text)}</span>{small}</div>")


def box(
    kind: str,
    body: str | Sequence[str],
    *,
    title: str | None = None,
    icon: str = "",
    ordered: bool = False,
    technical: str | None = None,
) -> None:
    """Help/notice box. ``kind``: green, blue, amber or red. Lists become bullets."""
    if isinstance(body, str):
        content = f"<div>{html.escape(body)}</div>"
    else:
        tag = "ol" if ordered else "ul"
        content = f"<{tag}>" + "".join(f"<li>{html.escape(item)}</li>" for item in body) + f"</{tag}>"
    head = f"<div class='gc-box-title'><span>{icon}</span><span>{html.escape(title)}</span></div>" if title else ""
    tech = f"<div class='gc-box-tech gc-ltr'>{html.escape(technical)}</div>" if technical else ""
    _md(f"<div class='gc-box gc-box-{kind}'>{head}{content}{tech}</div>")


@dataclass
class Card:
    icon: str
    label: str
    value: str
    tone: str = "info"  # good | warn | bad | info
    hint: str = ""
    badge: str | None = None


def cards(items: Iterable[Card]) -> None:
    parts = []
    for c in items:
        badge = c.badge or TONE_BADGE.get(c.tone, "")
        parts.append(
            f"<div class='gc-card gc-tone-{c.tone}'>"
            f"<span class='gc-badge'>{html.escape(badge)}</span>"
            f"<div class='gc-card-icon'>{c.icon}</div><div>"
            f"<div class='gc-card-label'>{html.escape(c.label)}</div>"
            f"<div class='gc-card-value'>{html.escape(c.value)}</div>"
            f"<div class='gc-card-hint'>{html.escape(c.hint)}</div></div></div>"
        )
    _md("<div class='gc-cards'>" + "".join(parts) + "</div>")


def category_bars(counts: dict[str, int], *, title: str, footnote: str) -> None:
    """Horizontal bar list of facility counts per category (one series, one hue)."""
    peak = max(counts.values(), default=0) or 1
    rows = []
    for key, count in counts.items():
        definition = config.CATEGORIES[key]
        label = category_label(key)
        width = 0 if count == 0 else max(2.0, 100.0 * count / peak)
        tooltip = f"{label}: {fa_digits(count)} مورد"
        rows.append(
            f"<div class='gc-bar-row' title='{html.escape(tooltip, quote=True)}'>"
            f"<div class='gc-bar-head'>"
            f"<div class='gc-bar-label'><span class='gc-dot' style='background:{definition.hex_color}'></span>"
            f"{definition.emoji} {html.escape(label)}</div>"
            f"<div class='gc-bar-value{' zero' if count == 0 else ''}'>{fa_digits(count)}</div></div>"
            f"<div class='gc-bar-track'><div class='gc-bar-fill' style='width:{width:.1f}%'></div></div></div>"
        )
    _md(
        f"<div class='gc-bars'><div class='gc-bars-title'>📊 {html.escape(title)}</div>"
        + "".join(rows)
        + f"<div class='gc-bars-foot'>{html.escape(footnote)}</div></div>"
    )
