"""Presentation layer for the English, left-to-right workspace."""

import streamlit as st


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], input, textarea, button {
  font-family: 'DM Sans', 'Segoe UI', sans-serif;
}
[data-testid="stAppViewContainer"] {background:#f5f7f7; color:#172b34; direction:ltr;}
[data-testid="stMainBlockContainer"] {max-width:1600px; padding:2.4rem 3.2rem 5rem;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stSidebar"] {background:#102a32; border-right:1px solid #28444a;}
[data-testid="stSidebar"] > div:first-child {background:transparent;}
[data-testid="stSidebarUserContent"] {padding:1.5rem 1.35rem 3rem;}
[data-testid="stSidebar"] label p, [data-testid="stSidebar"] p {color:#e2efed;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {font-size:.84rem;}
[data-testid="stSidebar"] [data-testid="stCheckbox"] {margin-bottom:.12rem;}
[data-testid="stSidebar"] [data-testid="stTextInput"] input {background:#f8fbfa; color:#172b34; border-radius:8px;}
[data-testid="stSidebar"] [data-testid="stTextInput"] input::placeholder {color:#738d87; opacity:1;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color:#a8c1bf;}
[data-testid="stSidebar"] hr {border-color:#315057; margin:1.25rem 0;}
button[data-testid^="stBaseButton-primary"] {background:#51d6aa !important; border:1px solid #51d6aa !important; color:#092a26 !important; font-weight:700 !important; border-radius:9px !important;}
button[data-testid^="stBaseButton-primary"]:hover {background:#83e8c5 !important; border-color:#83e8c5 !important;}
button[data-testid^="stBaseButton-secondary"] {border-radius:9px !important; font-weight:600 !important;}
[data-testid="stSidebar"] button[data-testid^="stBaseButton-secondary"] {background:#1a3940; border:1px solid #48646a; color:#e8f4f2;}
[data-testid="stSidebar"] button:disabled {opacity:.45 !important;}
button p {color:inherit !important;}
.en-brand {display:flex; gap:12px; align-items:center; padding:0 0 1.35rem; border-bottom:1px solid #365058;}
.en-brand, .en-side-kicker, .en-side-note, .en-hero, .en-heading, .en-step, .en-notice, .en-stat, .en-bars {font-family:'DM Sans','Segoe UI',sans-serif;}
.en-brand-mark {display:grid; place-items:center; width:41px; height:41px; border-radius:12px; background:#54d7ab; color:#102a32; font-size:22px; font-weight:800;}
.en-brand-name {font-family:'Manrope',sans-serif;color:#fff;font-size:17px;font-weight:800;letter-spacing:-.04em;}
.en-brand-sub {color:#9fbcb9;font-size:10px;letter-spacing:.14em;text-transform:uppercase;font-weight:700;margin-top:2px;}
.en-side-kicker {color:#68d7b3;font-size:10px;letter-spacing:.15em;text-transform:uppercase;font-weight:800;margin:1.35rem 0 .5rem;}
.en-side-note {color:#b5c9c7;font-size:12px;line-height:1.6;margin:.15rem 0 .6rem;}
.en-hero {background:#102f36; border-radius:22px; padding:2.6rem 3rem; position:relative; overflow:hidden; color:white; box-shadow:0 12px 34px rgba(18,55,59,.11);}
.en-hero:before {content:''; position:absolute; width:310px; height:310px; right:-15px; top:-115px; border-radius:50%; border:1px solid rgba(130,222,197,.18); box-shadow:0 0 0 45px rgba(130,222,197,.035),0 0 0 90px rgba(130,222,197,.035),0 0 0 135px rgba(130,222,197,.025);}
.en-eyebrow {color:#7de1c0; font-size:11px; letter-spacing:.16em; font-weight:800; text-transform:uppercase; position:relative;}
.en-hero h1 {font-family:'Manrope','Segoe UI',sans-serif; color:#fff; font-size:clamp(30px,3vw,46px); line-height:1.15; letter-spacing:-.05em; margin:.85rem 0 .8rem; max-width:760px; font-weight:800; position:relative;}
.en-hero p {color:#bed2d0; font-size:15px; line-height:1.75; max-width:680px; margin:0; position:relative;}
.en-hero-tags {display:flex; gap:.6rem; flex-wrap:wrap; margin-top:1.4rem; position:relative;}
.en-hero-tags span {color:#d7eee8; font-size:10px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; border:1px solid #4b7775; padding:.38rem .7rem; border-radius:99px;}
.en-heading {display:flex; align-items:end; justify-content:space-between; gap:1rem; margin:1.8rem 0 .85rem;}
.en-heading h2 {font-family:'Manrope',sans-serif;font-weight:800;font-size:21px;letter-spacing:-.04em;color:#183139;margin:0;}
.en-heading p {font-size:13px;color:#728487;margin:.2rem 0 0;}
.en-chip {font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#247960;background:#e1f6ed;padding:.4rem .7rem;border-radius:99px;white-space:nowrap;}
.en-steps {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;}
.en-step {background:white;border:1px solid #e1e9e7;border-radius:16px;padding:1.25rem 1.3rem;min-height:151px;box-shadow:0 3px 12px rgba(30,60,55,.035);}
.en-step-num {color:#18856a;background:#e8f8f1;border-radius:9px;font-size:11px;letter-spacing:.06em;font-weight:800;padding:7px 9px;display:inline-block;}
.en-step h3 {font-family:'Manrope',sans-serif;color:#203a3d;font-size:15px;letter-spacing:-.02em;margin:.9rem 0 .3rem;font-weight:800;}
.en-step p {color:#748587;font-size:12px;line-height:1.6;margin:0;}
.en-notice {background:#eaf4f1;border:1px solid #d4eae2;border-left:3px solid #45b998;border-radius:11px;padding:1rem 1.2rem;color:#446a61;font-size:13px;line-height:1.6;margin:1.1rem 0;}
.en-notice strong {color:#234f45;}
.en-stats {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:.25rem 0 1.15rem;}
.en-stat {background:white;border:1px solid #e0e9e6;border-radius:15px;padding:1.05rem 1.15rem;min-height:110px;}
.en-stat-label {color:#728582;font-size:10px;text-transform:uppercase;letter-spacing:.1em;font-weight:800;}
.en-stat-value {font-family:'Manrope',sans-serif;color:#173c36;font-weight:800;font-size:27px;letter-spacing:-.05em;margin-top:.25rem;line-height:1.2;}
.en-stat-hint {font-size:11px;color:#82908f;margin-top:.3rem;}
.en-bars {background:white;border:1px solid #e0e9e6;border-radius:15px;padding:1.15rem;}
.en-bars-title {font-family:'Manrope',sans-serif;color:#1d3b3a;font-weight:800;font-size:15px;margin-bottom:1rem;}
.en-bar {margin:.65rem 0;} .en-bar-head {display:flex;justify-content:space-between;gap:.5rem;color:#516964;font-size:11px;}
.en-bar-head b {color:#1c3d37;} .en-track {background:#edf3f1;border-radius:9px;height:6px;margin-top:.35rem;overflow:hidden;}
.en-fill {height:100%;border-radius:9px;background:#51c7a2;}
.en-bars-foot {color:#81918d;font-size:10px;line-height:1.5;margin-top:1rem;}
[data-testid="stTabs"] [role="tablist"] {gap:1.2rem;border-bottom:1px solid #dbe5e2;}
[data-testid="stTabs"] [role="tab"] {padding:.65rem .15rem !important;}
[data-testid="stTabs"] [role="tab"] p {font-family:'DM Sans',sans-serif;font-size:13px;font-weight:700;color:#718580;}
[data-testid="stTabs"] [aria-selected="true"] p {color:#176d58 !important;}
[data-baseweb="tab-highlight"] {background-color:#38b58c !important;}
iframe {border-radius:14px;}
@media(max-width:800px) {[data-testid="stMainBlockContainer"] {padding:1.5rem 1rem 3rem}.en-hero {padding:1.6rem}.en-steps,.en-stats {grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px) {.en-steps,.en-stats {grid-template-columns:1fr}.en-hero h1 {font-size:30px}}
</style>
"""


def apply_english_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
