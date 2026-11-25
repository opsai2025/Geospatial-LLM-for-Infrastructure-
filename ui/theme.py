"""Global CSS for the Persian RTL interface (follows the team's UI design rules).

Fonts, base sizes and colours are set in .streamlit/config.toml; this file
adds what the theme options cannot express: RTL layout with the sidebar on
the right, header/sidebar gradients, high-contrast bordered buttons, help
boxes, status cards and tabs.
"""

from __future__ import annotations

import streamlit as st

FONT_STACK = "BNazanin, 'B Nazanin', Vazirmatn, Tahoma, sans-serif"

CSS = f"""
<style>
/* ---------- RTL layout: sidebar on the right, all text right-aligned ---------- */
[data-testid="stAppViewContainer"] {{ direction: rtl; }}
[data-testid="stMain"], [data-testid="stSidebar"] {{ direction: rtl; text-align: right; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 2.5rem !important; max-width: 1480px; }}
[data-testid="stSidebarUserContent"] {{ padding-top: 0.5rem; }}
/* Left-to-right islands: code, technical identifiers, the map */
pre, code, [data-testid="stCode"], .gc-ltr {{ direction: ltr !important; text-align: left; }}
iframe {{ direction: ltr; border-radius: 14px; }}
input, textarea {{ font-family: {FONT_STACK}; }}

/* ---------- Sidebar (dark navy gradient) ---------- */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
    border-left: 1px solid #334155;
}}
[data-testid="stSidebar"] > div:first-child {{ background: transparent; }}
/* The sidebar sits on the right, so its collapse/expand arrows are mirrored */
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {{ transform: scaleX(-1); }}
.gc-brand {{
    display: flex; align-items: center; gap: .75rem;
    padding: .4rem .2rem 1rem; margin-bottom: .4rem; border-bottom: 1px solid #334155;
}}
.gc-brand-icon {{
    width: 46px; height: 46px; flex: 0 0 46px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center; font-size: 1.5rem;
    background: linear-gradient(135deg, #14b8a6 0%, #0e7490 100%);
    box-shadow: 0 4px 12px rgba(20, 184, 166, .35);
}}
.gc-brand-title {{ color: #ffffff; font-weight: 700; font-size: 1.15rem; line-height: 1.5; }}
.gc-brand-sub {{ color: #94a3b8; font-size: .85rem; }}
.gc-side-title {{
    display: flex; align-items: center; gap: .45rem;
    color: #4ed793; font-weight: 700; font-size: 1.02rem;
    margin: 1.1rem 0 .45rem; padding-bottom: .3rem; border-bottom: 1px dashed #334155;
}}
.gc-side-note {{ color: #cbd5e1; font-size: .88rem; line-height: 1.8; }}
.gc-side-region {{
    background: #1e293b; border: 1px solid #475569; border-radius: 10px;
    padding: .55rem .75rem; color: #f1f5f9; font-size: .95rem; margin: .4rem 0;
}}

/* ---------- Header ---------- */
.gc-header {{
    display: flex; align-items: center; gap: 1.1rem;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 16px; padding: 1.6rem 2rem; margin-bottom: 1.2rem;
    box-shadow: 0 8px 24px rgba(15, 23, 42, .25);
}}
.gc-header-icon {{
    font-size: 2.4rem; width: 64px; height: 64px; flex: 0 0 64px; border-radius: 16px;
    display: flex; align-items: center; justify-content: center; background: rgba(78, 215, 147, .12);
    border: 1px solid rgba(78, 215, 147, .35);
}}
.gc-header, .gc-header-text {{ direction: rtl; text-align: right; }}
.gc-header-text {{ flex: 1 1 auto; min-width: 0; }}
.gc-header-title {{ color: #4ed793; font-size: 2.2rem; font-weight: 700; line-height: 1.6; }}
.gc-header-sub {{ color: #e2e8f0; font-size: 1.2rem; line-height: 1.9; margin-top: .2rem; }}

/* ---------- Section titles ---------- */
.gc-section {{
    display: flex; align-items: center; gap: .55rem;
    font-size: 1.35rem; font-weight: 700; color: #0f172a; margin: 1.2rem 0 .6rem;
}}
.gc-section small {{ font-size: .9rem; font-weight: 400; color: #475569; margin-right: .4rem; }}

/* ---------- Help / info boxes ---------- */
.gc-box {{ border-radius: 12px; padding: .85rem 1.1rem; margin: .5rem 0 .8rem; line-height: 2; font-size: 1rem; }}
.gc-box-title {{ font-weight: 700; margin-bottom: .15rem; display: flex; gap: .4rem; align-items: center; }}
.gc-box, .gc-box ul, .gc-box ol, .gc-box li {{ direction: rtl; text-align: right; }}
.gc-box ul, .gc-box ol {{ margin: .2rem 1.2rem 0 0; padding: 0; }}
.gc-box ul li, .gc-box ol li {{ margin: .1rem 0; padding: 0 .35rem 0 0; }}
.gc-box-green {{ background-color: #daf39e; color: #000000; }}
.gc-box-blue  {{ background-color: rgba(28, 131, 255, .1); color: #0054A3; }}
.gc-box-amber {{ background-color: #fef3c7; color: #78350f; border-right: 5px solid #d97706; }}
.gc-box-red   {{ background-color: #fee2e2; color: #7f1d1d; border-right: 5px solid #a43232; }}
.gc-box-tech  {{ font-size: .8rem; color: #475569; margin-top: .3rem; }}

/* ---------- Status cards ---------- */
.gc-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .9rem; margin: .4rem 0 1rem; }}
.gc-card {{
    position: relative; display: flex; gap: .8rem; align-items: flex-start;
    background: #ffffff; border: 2px solid #cbd5e1; border-radius: 14px; padding: 1rem 1.05rem;
    box-shadow: 0 2px 8px rgba(15, 23, 42, .06);
}}
.gc-card-icon {{
    font-size: 1.45rem; width: 46px; height: 46px; flex: 0 0 46px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center; background: #f1f5f9;
}}
.gc-card-label {{ color: #334155; font-size: .95rem; font-weight: 700; }}
.gc-card-value {{ color: #0f172a; font-size: 1.85rem; font-weight: 700; line-height: 1.35; }}
.gc-card-hint {{ color: #475569; font-size: .85rem; line-height: 1.6; }}
.gc-badge {{
    position: absolute; top: .7rem; left: .8rem; border-radius: 999px; padding: .05rem .7rem;
    font-size: .78rem; font-weight: 700; color: #ffffff;
}}
.gc-tone-good    {{ border-color: #86efac; background: #f0fdf4; }}
.gc-tone-good    .gc-card-icon {{ background: #dcfce7; }}
.gc-tone-good    .gc-badge {{ background: #15803d; }}
.gc-tone-warn    {{ border-color: #fcd34d; background: #fffbeb; }}
.gc-tone-warn    .gc-card-icon {{ background: #fef3c7; }}
.gc-tone-warn    .gc-badge {{ background: #b45309; }}
.gc-tone-bad     {{ border-color: #fca5a5; background: #fef2f2; }}
.gc-tone-bad     .gc-card-icon {{ background: #fee2e2; }}
.gc-tone-bad     .gc-badge {{ background: #b91c1c; }}
.gc-tone-info    {{ border-color: #93c5fd; background: #eff6ff; }}
.gc-tone-info    .gc-card-icon {{ background: #dbeafe; }}
.gc-tone-info    .gc-badge {{ background: #1d4ed8; }}

/* ---------- Category bar list ---------- */
.gc-bars {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px; padding: .8rem .9rem; }}
.gc-bars-title {{ font-weight: 700; color: #0f172a; margin-bottom: .4rem; font-size: 1.05rem; }}
.gc-bar-row {{ padding: .3rem .4rem .4rem; border-radius: 8px; }}
.gc-bar-row:hover {{ background: #f1f5f9; }}
.gc-bar-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: .5rem; margin-bottom: .2rem; }}
.gc-bar-label {{ color: #1e293b; font-size: .92rem; line-height: 1.5; }}
.gc-dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-left: .35rem;
          box-shadow: 0 0 0 2px #ffffff; vertical-align: middle; }}
.gc-bar-track {{ height: 10px; background: #e2e8f0; border-radius: 4px; overflow: hidden; }}
.gc-bar-fill {{ height: 100%; background: #2563eb; border-top-left-radius: 4px; border-bottom-left-radius: 4px; }}
.gc-bar-value {{ color: #0f172a; font-weight: 700; text-align: left; font-size: .95rem; }}
.gc-bar-value.zero {{ color: #94a3b8; }}
.gc-bars-foot {{ color: #475569; font-size: .8rem; margin-top: .45rem; line-height: 1.7; }}

/* ---------- Buttons: high contrast + lighter border ---------- */
button[data-testid^="stBaseButton-primary"] {{
    background-color: #15803d !important; border: 3px solid #4ade80 !important; color: #ffffff !important;
    font-weight: 700 !important;
}}
button[data-testid^="stBaseButton-primary"]:hover {{ background-color: #166534 !important; }}
button[data-testid^="stBaseButton-secondary"] {{
    background-color: #1e293b !important; border: 2px solid #64748b !important; color: #ffffff !important;
}}
button[data-testid^="stBaseButton-secondary"]:hover {{ background-color: #334155 !important; border-color: #94a3b8 !important; }}
[data-testid="stDownloadButton"] button {{
    background-color: #1d4ed8 !important; border: 3px solid #60a5fa !important; color: #ffffff !important;
    font-weight: 700 !important;
}}
[data-testid="stDownloadButton"] button:hover {{ background-color: #1e40af !important; }}
button:disabled {{ opacity: .5 !important; }}
button p {{ color: inherit !important; }}

/* ---------- Tabs ---------- */
[data-testid="stTabs"] [role="tablist"] {{ gap: .45rem; border-bottom: 2px solid #cbd5e1; }}
[data-testid="stTabs"] [role="tab"] {{
    background: #ffffff; border: 1px solid #cbd5e1; border-bottom: 3px solid transparent;
    border-radius: 10px 10px 0 0; padding: .45rem 1.1rem !important; height: auto !important;
}}
[data-testid="stTabs"] [role="tab"]:hover {{ background: #f1f5f9; }}
[data-testid="stTabs"] [role="tab"] p {{ font-size: 1.02rem !important; font-weight: 700; color: #334155; }}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
    background: #1e293b; border-color: #1e293b; border-bottom-color: #ef4444;
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] p,
[data-testid="stTabs"] [role="tab"][aria-selected="true"] [data-testid="stIconMaterial"] {{ color: #ffffff; }}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{ display: none; }}

/* ---------- Simple HTML tables ---------- */
.gc-table {{ width: 100%; max-width: 640px; border-collapse: separate; border-spacing: 0; background: #ffffff;
            border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; margin: .4rem 0 1rem; }}
.gc-table th {{ background: #1e293b; color: #ffffff; padding: .5rem .9rem; text-align: right; font-weight: 700; }}
.gc-table td {{ padding: .42rem .9rem; border-top: 1px solid #e2e8f0; color: #0f172a; }}
.gc-table td.num {{ font-weight: 700; text-align: left; width: 9rem; }}
.gc-table tr:last-child td {{ background: #f0fdf4; font-weight: 700; }}

/* ---------- Misc ---------- */
[data-testid="stExpander"] summary p {{ font-weight: 700; }}
[data-testid="stCaptionContainer"] {{ font-size: .88rem; }}
</style>
"""


def apply_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
