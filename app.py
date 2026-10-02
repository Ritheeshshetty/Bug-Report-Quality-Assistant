"""
app.py – Bug Report Quality Assistant
Streamlit UI entry point.

Features:
  • Dropdown to select sample bug reports or paste custom text.
  • Visual score gauges and colour-coded grade badges.
  • Highlighted missing-field alert banners grouped by severity.
  • Side-by-side comparison: original vs. ISTQB-rewritten report.
  • JSON export of the full triage evaluation.
  • Works fully offline (rule-based rewriter) or with OpenAI key (AI rewrite).
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

# ── Ensure src/ is importable when running from project root ──────────────────
sys.path.insert(0, str(Path(__file__).parent))

from src.models import BugReport, RewrittenBug, ScoreResult
from src.scoring_engine import score_bug_report
from src.ai_rewriter import rewrite_bug_report

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(name)s │ %(message)s")

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Bug Report Quality Assistant",
    page_icon="🐛",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — premium dark-mode design
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  /* ── Google Font ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  /* ── Global background ── */
  .stApp { background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%); }

  /* ── Top header / toolbar bar ── */
  [data-testid="stHeader"],
  [data-testid="stToolbar"],
  header[data-testid="stHeader"],
  .stApp > header,
  .stAppHeader,
  section[data-testid="stSidebarContent"] ~ div > header {
    background-color: #0d1117 !important;
    background: #0d1117 !important;
    border-bottom: 1px solid #21262d !important;
  }
  /* Deploy button & toolbar icons */
  [data-testid="stHeader"] button,
  [data-testid="stToolbar"] button,
  [data-testid="stDeployButton"],
  [data-testid="stDeployButton"] button,
  [data-testid="stHeader"] a,
  [data-testid="baseButton-headerNoPadding"],
  [data-testid="stStatusWidget"] {
    color: #8b949e !important;
    background-color: transparent !important;
  }
  [data-testid="stDeployButton"] button:hover,
  [data-testid="stHeader"] button:hover {
    color: #c9d1d9 !important;
    background-color: rgba(255,255,255,0.05) !important;
  }
  /* Streamlit top-right menu (⋮) popover */
  [data-testid="stMainMenu"] ul,
  ul[data-testid="main-menu-list"] {
    background-color: #1c2128 !important;
    border: 1px solid #30363d !important;
  }
  [data-testid="stMainMenu"] li,
  ul[data-testid="main-menu-list"] li {
    color: #c9d1d9 !important;
  }
  [data-testid="stMainMenu"] li:hover,
  ul[data-testid="main-menu-list"] li:hover {
    background-color: rgba(88,166,255,0.1) !important;
    color: #58a6ff !important;
  }

  /* ── BaseWeb dropdown / listbox portal (selectbox options) ── */
  /* These render in a portal at the body root, outside .stApp */
  [role="listbox"],
  [role="option"],
  ul[role="listbox"],
  li[role="option"] {
    background-color: #1c2128 !important;
    color: #c9d1d9 !important;
  }
  li[role="option"]:hover,
  li[role="option"][aria-selected="true"] {
    background-color: rgba(88,166,255,0.15) !important;
    color: #58a6ff !important;
  }
  /* BaseWeb popover container */
  [data-baseweb="popover"],
  div[data-baseweb="popover"] > div,
  div[data-baseweb="select-dropdown"],
  [data-baseweb="menu"] {
    background-color: #1c2128 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.6) !important;
  }
  /* Every item inside BaseWeb menu */
  [data-baseweb="menu"] [role="option"],
  [data-baseweb="menu"] li,
  [data-baseweb="menu"] [data-baseweb="menu-item"] {
    background-color: #1c2128 !important;
    color: #c9d1d9 !important;
  }
  [data-baseweb="menu"] [role="option"]:hover,
  [data-baseweb="menu"] li:hover,
  [data-baseweb="menu"] [data-baseweb="menu-item"]:hover,
  [data-baseweb="menu"] [aria-selected="true"] {
    background-color: rgba(88,166,255,0.15) !important;
    color: #58a6ff !important;
  }
  /* Catch-all: any white card/surface that appears during interaction */
  div[class*="Popover"],
  div[class*="popover"],
  div[class*="Dropdown"],
  div[class*="dropdown"],
  div[class*="Menu"],
  div[class*="menu"] > ul,
  div[class*="SelectMenu"],
  div[class*="List"] > ul {
    background-color: #1c2128 !important;
    color: #c9d1d9 !important;
    border-color: #30363d !important;
  }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
    border-right: 1px solid #30363d;
  }
  [data-testid="stSidebar"] .stMarkdown h2,
  [data-testid="stSidebar"] .stMarkdown h3 {
    color: #58a6ff;
  }

  /* ── Hero header ── */
  .hero-header {
    background: linear-gradient(135deg, #1a2332 0%, #0d1117 40%, #1a1f2e 100%);
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
  }
  .hero-header::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(circle at 20% 50%, rgba(88,166,255,0.08) 0%, transparent 60%),
                radial-gradient(circle at 80% 50%, rgba(139,92,246,0.08) 0%, transparent 60%);
    pointer-events: none;
  }
  .hero-title {
    font-size: 2.4rem; font-weight: 800;
    background: linear-gradient(135deg, #58a6ff 0%, #a78bfa 50%, #34d399 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 0.3rem;
  }
  .hero-subtitle { color: #8b949e; font-size: 1rem; font-weight: 400; }
  .hero-badges { display: flex; gap: 0.5rem; margin-top: 0.8rem; flex-wrap: wrap; }
  .hero-badge {
    background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.3);
    color: #58a6ff; border-radius: 20px; padding: 0.2rem 0.75rem;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em;
  }
  .hero-badge.purple {
    background: rgba(139,92,246,0.1); border-color: rgba(139,92,246,0.3); color: #a78bfa;
  }
  .hero-badge.green {
    background: rgba(52,211,153,0.1); border-color: rgba(52,211,153,0.3); color: #34d399;
  }

  /* ── Score gauge card ── */
  .score-card {
    background: linear-gradient(135deg, #1c2128 0%, #161b22 100%);
    border: 1px solid #30363d; border-radius: 14px;
    padding: 1.6rem; text-align: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    position: relative; overflow: hidden;
  }
  .score-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: var(--accent-grad, linear-gradient(90deg, #58a6ff, #a78bfa));
  }
  .score-card:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.4); }
  .score-value { font-size: 3.5rem; font-weight: 800; color: var(--accent, #58a6ff); }
  .score-label { font-size: 0.78rem; color: #8b949e; text-transform: uppercase;
                 letter-spacing: 0.1em; margin-top: 0.2rem; }
  .score-sub { font-size: 0.85rem; color: #c9d1d9; margin-top: 0.4rem; }

  /* ── Grade badge ── */
  .grade-badge {
    display: inline-block; padding: 0.35rem 1rem; border-radius: 20px;
    font-weight: 700; font-size: 0.9rem; letter-spacing: 0.05em; margin-top: 0.6rem;
  }
  .grade-excellent { background: rgba(52,211,153,0.15); border: 1px solid rgba(52,211,153,0.4);
                     color: #34d399; }
  .grade-good      { background: rgba(88,166,255,0.15); border: 1px solid rgba(88,166,255,0.4);
                     color: #58a6ff; }
  .grade-needs     { background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.4);
                     color: #f59e0b; }
  .grade-poor      { background: rgba(248,81,73,0.15); border: 1px solid rgba(248,81,73,0.4);
                     color: #f85149; }

  /* ── Alert banners ── */
  .alert-banner {
    border-radius: 10px; padding: 0.8rem 1rem; margin-bottom: 0.5rem;
    display: flex; align-items: flex-start; gap: 0.6rem;
    font-size: 0.87rem; line-height: 1.5;
    animation: slideIn 0.3s ease;
  }
  @keyframes slideIn { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; } }
  .alert-error   { background: rgba(248,81,73,0.1); border: 1px solid rgba(248,81,73,0.35);
                   color: #ffa198; }
  .alert-warning { background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.35);
                   color: #ffc107; }
  .alert-info    { background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.3);
                   color: #79c0ff; }
  .alert-icon    { flex-shrink: 0; font-size: 1rem; margin-top: 0.05rem; }
  .alert-field   { font-weight: 700; font-family: 'JetBrains Mono', monospace;
                   font-size: 0.78rem; opacity: 0.9; }
  .alert-msg     { color: inherit; }
  .alert-tip     { font-size: 0.8rem; opacity: 0.75; margin-top: 0.2rem; font-style: italic; }

  /* ── Section headers ── */
  .section-header {
    font-size: 1.05rem; font-weight: 700; color: #c9d1d9;
    border-bottom: 1px solid #30363d; padding-bottom: 0.5rem; margin-bottom: 1rem;
    display: flex; align-items: center; gap: 0.5rem;
  }

  /* ── Report comparison panels ── */
  .report-panel {
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 1.4rem; height: 100%;
  }
  .report-panel-title {
    font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em;
    margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #21262d;
  }
  .original-title  { color: #f85149; }
  .rewritten-title { color: #3fb950; }
  .field-label {
    font-size: 0.72rem; font-weight: 700; color: #8b949e; text-transform: uppercase;
    letter-spacing: 0.08em; margin-bottom: 0.2rem; margin-top: 0.8rem;
  }
  .field-value {
    font-size: 0.88rem; color: #c9d1d9; background: #0d1117;
    border: 1px solid #21262d; border-radius: 6px; padding: 0.5rem 0.7rem;
  }
  .field-value.mono { font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; }
  .empty-field { color: #6e7681; font-style: italic; }
  .improvement-chip {
    display: inline-block; background: rgba(52,211,153,0.1);
    border: 1px solid rgba(52,211,153,0.3); color: #34d399;
    border-radius: 12px; padding: 0.15rem 0.55rem; font-size: 0.75rem;
    margin: 0.15rem 0.15rem 0 0;
  }

  /* ── Progress bar colours ── */
  .stProgress > div > div > div > div { border-radius: 8px; }

  /* ── Dividers ── */
  hr { border-color: #21262d; }

  /* ── Source badge ── */
  .source-badge {
    display: inline-flex; align-items: center; gap: 0.3rem;
    padding: 0.25rem 0.75rem; border-radius: 20px;
    font-size: 0.75rem; font-weight: 600;
  }
  .source-ai   { background: rgba(139,92,246,0.15); border: 1px solid rgba(139,92,246,0.35);
                 color: #c084fc; }
  .source-rule { background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.3);
                 color: #58a6ff; }

  /* ── Sidebar metric card ── */
  .sidebar-metric {
    background: rgba(88,166,255,0.05); border: 1px solid #30363d; border-radius: 10px;
    padding: 0.8rem 1rem; margin-bottom: 0.5rem;
  }
  .sidebar-metric-label { font-size: 0.72rem; color: #8b949e; text-transform: uppercase;
                          letter-spacing: 0.08em; }
  .sidebar-metric-value { font-size: 1.4rem; font-weight: 700; color: #c9d1d9; }

  /* ── Force dark on ALL native Streamlit widgets ── */

  /* General text & labels */
  label, .stMarkdown, .stText, p, span, li { color: #c9d1d9; }

  /* Selectbox / dropdown */
  [data-testid="stSelectbox"] > div > div,
  [data-testid="stSelectbox"] > div > div > div,
  div[data-baseweb="select"] > div,
  div[data-baseweb="select"] div[class*="ValueContainer"],
  div[data-baseweb="select"] div[class*="singleValue"],
  div[data-baseweb="select"] div[class*="placeholder"] {
    background-color: #161b22 !important;
    color: #c9d1d9 !important;
    border-color: #30363d !important;
  }
  div[data-baseweb="select"] > div:focus-within,
  div[data-baseweb="select"] > div:hover {
    border-color: #58a6ff !important;
  }
  /* Dropdown popover list */
  div[data-baseweb="popover"] ul,
  div[data-baseweb="menu"],
  div[data-baseweb="menu"] ul {
    background-color: #1c2128 !important;
    border: 1px solid #30363d !important;
  }
  div[data-baseweb="menu"] li,
  div[data-baseweb="option"] {
    color: #c9d1d9 !important;
    background-color: #1c2128 !important;
  }
  div[data-baseweb="menu"] li:hover,
  div[data-baseweb="option"]:hover {
    background-color: rgba(88,166,255,0.12) !important;
    color: #58a6ff !important;
  }

  /* Text area */
  textarea,
  [data-testid="stTextArea"] textarea {
    background-color: #161b22 !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
  }
  textarea:focus,
  [data-testid="stTextArea"] textarea:focus {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 2px rgba(88,166,255,0.15) !important;
  }

  /* Text input */
  input[type="text"],
  input[type="number"],
  input[type="password"],
  [data-testid="stTextInput"] input,
  [data-testid="stNumberInput"] input {
    background-color: #161b22 !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
  }
  [data-testid="stTextInput"] input:focus,
  [data-testid="stNumberInput"] input:focus {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 2px rgba(88,166,255,0.15) !important;
  }

  /* Radio buttons */
  [data-testid="stRadio"] label,
  [data-testid="stRadio"] div { color: #c9d1d9 !important; }

  /* Checkbox */
  [data-testid="stCheckbox"] label { color: #c9d1d9 !important; }

  /* Expander */
  [data-testid="stExpander"] {
    background-color: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
  }
  [data-testid="stExpander"] summary,
  [data-testid="stExpander"] summary span,
  [data-testid="stExpander"] summary p {
    color: #c9d1d9 !important;
    background-color: #161b22 !important;
  }
  [data-testid="stExpander"] > div[data-testid="stVerticalBlock"] {
    background-color: #161b22 !important;
  }

  /* Code / pre blocks — target every Streamlit code layer */
  pre, code,
  [data-testid="stCode"],
  [data-testid="stCode"] > div,
  [data-testid="stCode"] pre,
  [data-testid="stCode"] code,
  [data-testid="stCodeBlock"],
  [data-testid="stCodeBlock"] > div,
  [data-testid="stCodeBlock"] pre,
  [data-testid="stCodeBlock"] code,
  .stCode, .stCode > div, .stCode pre, .stCode code,
  div[class*="stCode"] pre,
  div[class*="stCode"] code {
    background-color: #0d1117 !important;
    background: #0d1117 !important;
    color: #c9d1d9 !important;
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
  }
  /* Copy button area inside code block */
  [data-testid="stCode"] > div:first-child,
  [data-testid="stCodeBlock"] > div:first-child {
    background-color: #0d1117 !important;
    border-bottom: 1px solid #21262d !important;
  }

  /* Text input — target all layers */
  [data-testid="stTextInput"],
  [data-testid="stTextInput"] > div,
  [data-testid="stTextInput"] > div > div,
  [data-baseweb="input"],
  [data-baseweb="input"] > div,
  [data-baseweb="base-input"],
  input[type="text"],
  input[type="number"],
  input[type="password"] {
    background-color: #161b22 !important;
    background: #161b22 !important;
    color: #c9d1d9 !important;
    border-color: #30363d !important;
    border-radius: 8px !important;
  }
  [data-baseweb="input"]:focus-within,
  [data-baseweb="input"] > div:focus-within {
    border-color: #58a6ff !important;
    box-shadow: 0 0 0 2px rgba(88,166,255,0.15) !important;
  }
  input::placeholder { color: #6e7681 !important; }


  /* st.info / st.success / st.warning / st.error callouts */
  [data-testid="stAlert"] {
    background-color: #161b22 !important;
    border-color: #30363d !important;
    color: #c9d1d9 !important;
  }

  /* Metric widget */
  [data-testid="stMetric"] label { color: #8b949e !important; }
  [data-testid="stMetric"] [data-testid="stMetricValue"] { color: #c9d1d9 !important; }
  [data-testid="stMetric"] [data-testid="stMetricDelta"] { color: #34d399 !important; }

  /* DataFrame / table */
  [data-testid="stDataFrame"] table,
  [data-testid="stDataFrame"] thead,
  [data-testid="stDataFrame"] tbody,
  [data-testid="stDataFrame"] th,
  [data-testid="stDataFrame"] td {
    background-color: #161b22 !important;
    color: #c9d1d9 !important;
    border-color: #30363d !important;
  }
  [data-testid="stDataFrame"] th { background-color: #1c2128 !important; color: #58a6ff !important; }

  /* Buttons */
  [data-testid="stButton"] > button {
    background-color: #1c2128 !important;
    color: #c9d1d9 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
  }
  [data-testid="stButton"] > button:hover {
    border-color: #58a6ff !important;
    color: #58a6ff !important;
    background-color: rgba(88,166,255,0.08) !important;
  }
  [data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #f97316, #ef4444) !important;
    color: #fff !important; border: none !important;
  }

  /* Slider */
  [data-testid="stSlider"] div[data-baseweb="slider"] div { background-color: #30363d !important; }
  [data-testid="stSlider"] [data-testid="stThumbValue"] { color: #c9d1d9 !important; }

  /* Tabs */
  button[data-baseweb="tab"] {
    color: #8b949e !important;
    background-color: transparent !important;
    border-bottom: 2px solid transparent !important;
  }
  button[data-baseweb="tab"][aria-selected="true"] {
    color: #58a6ff !important;
    border-bottom-color: #58a6ff !important;
  }
  [data-baseweb="tab-panel"] { background-color: transparent !important; }

  /* Multiselect tags */
  [data-baseweb="tag"] {
    background-color: rgba(88,166,255,0.15) !important;
    color: #58a6ff !important;
  }

  /* JSON viewer */
  [data-testid="stJson"] { background-color: #0d1117 !important; border: 1px solid #21262d !important; border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

DATA_PATH = Path(__file__).parent / "data" / "sample_bugs.json"


@st.cache_data(show_spinner=False)
def load_sample_bugs() -> List[Dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


SAMPLE_BUGS = load_sample_bugs()


def parse_bug_from_dict(data: Dict[str, Any]) -> BugReport:
    """
    Normalise common JSON field aliases before constructing a BugReport.
    This makes the JSON input format lenient — users can use 'title', 'steps',
    'expected', 'actual', etc. and they will be mapped to the correct field names.
    Unknown keys are silently dropped to prevent Pydantic validation errors.
    """
    # Mapping: alias (lower-cased) → canonical BugReport field name
    _ALIAS: Dict[str, str] = {
        # id
        "bug_id": "id",
        "defect_id": "id",
        "ticket_id": "id",
        # summary
        "title": "summary",
        "headline": "summary",
        "subject": "summary",
        "short_description": "summary",
        # description
        "details": "description",
        "body": "description",
        "narrative": "description",
        "detail": "description",
        # steps_to_reproduce
        "steps": "steps_to_reproduce",
        "reproduction_steps": "steps_to_reproduce",
        "steps_to_reproduce": "steps_to_reproduce",
        "how_to_reproduce": "steps_to_reproduce",
        "repro_steps": "steps_to_reproduce",
        # expected_result
        "expected": "expected_result",
        "expected_behavior": "expected_result",
        "expected_results": "expected_result",
        # actual_result
        "actual": "actual_result",
        "actual_behavior": "actual_result",
        "actual_results": "actual_result",
        "observed": "actual_result",
        "observed_behavior": "actual_result",
        # environment
        "env": "environment",
        "environment_details": "environment",
        # severity / priority
        "sev": "severity",
        "pri": "priority",
        "prio": "priority",
        # reporter
        "author": "reporter",
        "reported_by": "reporter",
        "submitter": "reporter",
    }

    # Known BugReport fields (to filter out unknown keys)
    _KNOWN = {
        "id", "label", "summary", "description", "steps_to_reproduce",
        "expected_result", "actual_result", "environment",
        "severity", "priority", "reporter", "attachments",
    }

    normalised: Dict[str, Any] = {}
    for raw_key, value in data.items():
        canonical = _ALIAS.get(raw_key.lower().strip(), raw_key.lower().strip())
        if canonical in _KNOWN:
            normalised[canonical] = value
        # else: silently drop unknown keys

    # Ensure steps_to_reproduce is always a list
    steps = normalised.get("steps_to_reproduce")
    if isinstance(steps, str):
        # Handle comma-separated or newline-separated strings
        if "\n" in steps:
            normalised["steps_to_reproduce"] = [s.strip() for s in steps.splitlines() if s.strip()]
        else:
            normalised["steps_to_reproduce"] = [s.strip() for s in steps.split(",") if s.strip()]

    return BugReport(**normalised)


def parse_bug_from_text(raw_text: str, bug_id: str = "CUSTOM-001") -> BugReport:
    """
    Best-effort parser to extract fields from free-form text input.

    Handles three formats:
      - JSON object: parsed directly via parse_bug_from_dict.
      - Block format:  "Field:\\n<content on next lines>"
      - Inline format: "Field: <content on same line>" for ALL known fields,
        including multi-word keys like "Steps to Reproduce", "Expected Result", etc.
    """
    # ── JSON detection ────────────────────────────────────────────────────────
    stripped_input = raw_text.strip()
    if stripped_input.startswith("{") and stripped_input.endswith("}"):
        try:
            data = json.loads(stripped_input)
            if isinstance(data, dict):
                # ── Detect full export payload (has original_report key) ──────
                # When the user pastes the JSON exported by this tool, unwrap
                # the original_report section and use that as the bug report.
                if "original_report" in data and isinstance(data["original_report"], dict):
                    data = data["original_report"]

                # Inject the custom bug_id only if no id/bug_id is present
                if "id" not in data and "bug_id" not in data:
                    data["id"] = bug_id
                return parse_bug_from_dict(data)
        except json.JSONDecodeError:
            pass  # Not valid JSON — fall through to text parser
    lines = raw_text.strip().splitlines()
    fields: Dict[str, Any] = {
        "id": bug_id,
        "summary": "",
        "description": "",
        "steps_to_reproduce": [],
        "expected_result": "",
        "actual_result": "",
        "environment": {},
        "severity": "",
        "priority": "",
        "reporter": "custom_input",
    }

    current_section: Optional[str] = None
    buffer: List[str] = []

    section_map = {
        "summary": "summary",
        "title": "summary",
        "description": "description",
        "details": "description",
        "steps to reproduce": "steps",
        "steps": "steps",
        "reproduction steps": "steps",
        "how to reproduce": "steps",
        "expected": "expected_result",
        "expected result": "expected_result",
        "expected behavior": "expected_result",
        "actual": "actual_result",
        "actual result": "actual_result",
        "actual behavior": "actual_result",
        "environment": "environment",
        "env": "environment",
        "severity": "severity",
        "priority": "priority",
    }

    # Build a regex from ALL known keys (longest first so multi-word keys win).
    _sorted_keys = sorted(section_map.keys(), key=len, reverse=True)
    _inline_re = re.compile(
        r"^(" + "|".join(re.escape(k) for k in _sorted_keys) + r")\s*:\s*(.+)$",
        re.IGNORECASE,
    )

    def flush(section: Optional[str], buf: List[str]) -> None:
        text = "\n".join(buf).strip()
        if not section or not text:
            return
        if section == "steps":
            # Support comma-separated steps on a single line
            if len(buf) == 1 and "," in text and not re.search(r"^\s*\d+[.)]\s*", text):
                step_lines = [s.strip() for s in text.split(",") if s.strip()]
            else:
                step_lines = [l for l in text.splitlines() if l.strip()]
            fields["steps_to_reproduce"].extend(step_lines)
        elif section == "environment":
            for line in text.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    fields["environment"][k.strip().lower().replace(" ", "_")] = v.strip()
        elif section in fields:
            existing = fields.get(section, "")
            fields[section] = (existing + "\n" + text).strip() if existing else text

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # ── Markdown heading OR bare "Field:" header (content on NEXT line) ──
        # Also matches bare known keywords alone on a line (e.g. just "Summary")
        header_match = re.match(r"^#{1,3}\s*(.+)$|^([A-Za-z ()]+)\s*:?\s*$", stripped)
        if header_match:
            detected = (header_match.group(1) or header_match.group(2) or "").strip().lower()
            # Only treat as a section header if detected text is a known keyword.
            # This prevents random words / short content from being misread as headers.
            if detected in section_map:
                flush(current_section, buffer)
                current_section = section_map[detected]
                buffer = []
                continue
            # Not a known keyword — fall through to buffer

        # ── Inline "Field: value" — ALL known section_map keys ───────────────
        inline_match = _inline_re.match(stripped)
        if inline_match:
            fname = inline_match.group(1).lower()
            fval  = inline_match.group(2).strip()
            mapped = section_map.get(fname, fname)
            flush(current_section, buffer)
            current_section = None
            buffer = []
            if mapped == "environment":
                fields["environment"]["raw"] = fval
            elif mapped == "steps":
                # Split numbered inline steps like "1. Do this, 2. Do that"
                if re.search(r"\d+\.", fval):
                    step_lines = re.split(r",\s*(?=\d+\.)", fval)
                else:
                    step_lines = [s.strip() for s in fval.split(",") if s.strip()]
                fields["steps_to_reproduce"].extend(step_lines)
            elif mapped in fields:
                fields[mapped] = fval
            continue

        buffer.append(line)

    flush(current_section, buffer)

    # If nothing was sectioned, treat the whole text as description + summary
    if not fields["summary"] and not fields["description"]:
        first_line = lines[0].strip() if lines else ""
        rest = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        fields["summary"] = first_line[:120]
        fields["description"] = rest or first_line

    return BugReport(**fields)



# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

def render_hero() -> None:
    st.markdown("""
    <div class="hero-header">
      <div class="hero-title">🐛 Bug Report Quality Assistant</div>
      <div class="hero-subtitle">
        ISTQB CTFL v4.0.1 §5.5 compliant scoring, alerting &amp; AI-powered rewriting
      </div>
      <div class="hero-badges">
        <span class="hero-badge">IGS Hackathon 2026</span>
        <span class="hero-badge purple">ISTQB CTFL v4.0.1</span>
        <span class="hero-badge green">Offline-Ready</span>
        <span class="hero-badge">Pydantic v2</span>
        <span class="hero-badge purple">GPT-4o / Rule-Based</span>
      </div>
    </div>
    """, unsafe_allow_html=True)


def render_score_card(
    label: str, value: float, max_val: float, accent: str, grad: str
) -> None:
    pct = value / max_val if max_val else 0
    st.markdown(f"""
    <div class="score-card" style="--accent:{accent}; --accent-grad:{grad};">
      <div class="score-value">{value:.1f}</div>
      <div class="score-label">{label}</div>
      <div class="score-sub">of {max_val:.0f}</div>
    </div>
    """, unsafe_allow_html=True)
    st.progress(min(pct, 1.0))


def grade_css_class(grade: str) -> str:
    mapping = {
        "Excellent": "grade-excellent",
        "Good": "grade-good",
        "Needs Improvement": "grade-needs",
        "Poor": "grade-poor",
    }
    return mapping.get(grade, "grade-poor")


def render_grade(score: float, grade: str) -> None:
    cls = grade_css_class(grade)
    emoji = {"Excellent": "🏆", "Good": "✅", "Needs Improvement": "⚠️", "Poor": "❌"}.get(grade, "")
    st.markdown(f"""
    <div style="text-align:center; margin-bottom:1rem;">
      <div class="score-value" style="color: var(--accent, #58a6ff); font-size:4rem;">{score:.0f}</div>
      <div class="score-label" style="font-size:0.9rem; color:#8b949e; margin-bottom:0.4rem;">
        Quality Score (0 – 100)
      </div>
      <span class="grade-badge {cls}">{emoji} {grade}</span>
    </div>
    """, unsafe_allow_html=True)


def render_alerts(score_result: ScoreResult) -> None:
    errors   = [a for a in score_result.alerts if a.severity == "error"]
    warnings = [a for a in score_result.alerts if a.severity == "warning"]
    infos    = [a for a in score_result.alerts if a.severity == "info"]

    if not (errors or warnings or infos):
        st.markdown("""
        <div class="alert-banner alert-info">
          <span class="alert-icon">✨</span>
          <div><span class="alert-msg">No quality alerts — this report meets all ISTQB criteria.</span></div>
        </div>
        """, unsafe_allow_html=True)
        return

    total = len(errors) + len(warnings) + len(infos)
    st.markdown(
        f"<div style='color:#8b949e; font-size:0.82rem; margin-bottom:0.6rem;'>"
        f"{total} alert(s) — "
        f"<span style='color:#f85149;'>🔴 {len(errors)} error(s)</span>, "
        f"<span style='color:#f59e0b;'>🟡 {len(warnings)} warning(s)</span>, "
        f"<span style='color:#58a6ff;'>🔵 {len(infos)} info</span>"
        f"</div>",
        unsafe_allow_html=True
    )

    for alert in errors + warnings + infos:
        icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(alert.severity, "ℹ️")
        css = {"error": "alert-error", "warning": "alert-warning", "info": "alert-info"}.get(
            alert.severity, "alert-info"
        )
        tip_html = (
            f'<div class="alert-tip">💡 {alert.suggestion}</div>'
            if alert.suggestion else ""
        )
        st.markdown(f"""
        <div class="alert-banner {css}">
          <span class="alert-icon">{icon}</span>
          <div>
            <span class="alert-field">[{alert.field_name}]</span>
            <span class="alert-msg"> {alert.message}</span>
            {tip_html}
          </div>
        </div>
        """, unsafe_allow_html=True)


def _val(text: str, mono: bool = False) -> str:
    if not text or not text.strip():
        return '<span class="empty-field">(not provided)</span>'
    cls = "field-value mono" if mono else "field-value"
    return f'<div class="{cls}">{text}</div>'


def _steps_html(steps: List[str]) -> str:
    if not steps:
        return '<span class="empty-field">(not provided)</span>'
    # Strip any leading number prefix (e.g. "1.", "1)", "1 -", "1 ")
    # so the <ol> list numbering doesn't double up with numbers in the text.
    _num_prefix = re.compile(r"^\s*\d+[.):\-]?\s*")
    cleaned = [_num_prefix.sub("", s).strip() for s in steps]
    items = "".join(
        f'<li style="margin-bottom:0.3rem; color:#c9d1d9;">{s}</li>' for s in cleaned
    )
    return f'<ol style="margin:0; padding-left:1.2rem; font-size:0.87rem;">{items}</ol>'


def render_env(env_dict: Dict[str, Any]) -> str:
    if not env_dict:
        return '<span class="empty-field">(not provided)</span>'
    rows = "".join(
        f'<tr><td style="color:#8b949e; font-size:0.78rem; padding:0.15rem 0.5rem 0.15rem 0;">'
        f'{k}</td><td style="color:#c9d1d9; font-size:0.82rem;">{v}</td></tr>'
        for k, v in env_dict.items() if v and k != "extra"
    )
    return f'<table style="width:100%; border-collapse:collapse;">{rows}</table>'


def render_comparison(bug: BugReport, rewritten: RewrittenBug) -> None:
    col_orig, col_rw = st.columns(2)

    # Environment dicts
    orig_env = (
        bug.environment if isinstance(bug.environment, dict)
        else bug.environment.model_dump(exclude_none=True, exclude={"extra"})
    )
    rw_env = rewritten.environment.model_dump(exclude_none=True, exclude={"extra"})
    orig_steps = bug.steps_to_reproduce
    rw_steps = rewritten.steps_to_reproduce

    # Source badge
    if rewritten.rewrite_source.value == "ai":
        badge = '<span class="source-badge source-ai">🤖 AI Rewrite (GPT-4o)</span>'
    else:
        badge = '<span class="source-badge source-rule">⚙️ Rule-Based Rewrite</span>'

    # Improvements
    chips = "".join(
        f'<span class="improvement-chip">✓ {imp}</span>'
        for imp in rewritten.improvements_made
    )

    with col_orig:
        st.markdown("""
        <div class="report-panel">
          <div class="report-panel-title original-title">📋 ORIGINAL REPORT</div>
        """, unsafe_allow_html=True)

        for field_label, content, mono in [
            ("Summary", bug.summary, False),
            ("Description", bug.description, False),
            ("Expected Result", bug.expected_result, False),
            ("Actual Result", bug.actual_result, False),
            ("Severity", bug.severity, True),
            ("Priority", bug.priority, True),
        ]:
            st.markdown(f'<div class="field-label">{field_label}</div>'
                        f'{_val(content, mono)}', unsafe_allow_html=True)

        st.markdown('<div class="field-label">Steps to Reproduce</div>', unsafe_allow_html=True)
        st.markdown(_steps_html(orig_steps), unsafe_allow_html=True)

        st.markdown('<div class="field-label">Environment</div>', unsafe_allow_html=True)
        st.markdown(render_env(orig_env), unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    with col_rw:
        st.markdown(f"""
        <div class="report-panel">
          <div class="report-panel-title rewritten-title">
            ✨ REWRITTEN REPORT &nbsp;&nbsp; {badge}
          </div>
        """, unsafe_allow_html=True)

        for field_label, content, mono in [
            ("Summary", rewritten.summary, False),
            ("Description", rewritten.description, False),
            ("Expected Result", rewritten.expected_result, False),
            ("Actual Result", rewritten.actual_result, False),
            ("Severity", rewritten.severity, True),
            ("Priority", rewritten.priority, True),
        ]:
            st.markdown(f'<div class="field-label">{field_label}</div>'
                        f'{_val(content, mono)}', unsafe_allow_html=True)

        st.markdown('<div class="field-label">Steps to Reproduce</div>', unsafe_allow_html=True)
        st.markdown(_steps_html(rw_steps), unsafe_allow_html=True)

        st.markdown('<div class="field-label">Environment</div>', unsafe_allow_html=True)
        st.markdown(render_env(rw_env), unsafe_allow_html=True)

        if chips:
            st.markdown(
                f'<div class="field-label" style="margin-top:1rem;">Improvements Applied</div>'
                f'<div style="margin-top:0.3rem;">{chips}</div>',
                unsafe_allow_html=True
            )

        st.markdown("</div>", unsafe_allow_html=True)


def build_export_payload(
    bug: BugReport,
    score_result: ScoreResult,
    rewritten: RewrittenBug,
) -> Dict[str, Any]:
    return {
        "export_metadata": {
            "tool": "Bug Report Quality Assistant",
            "standard": "ISTQB CTFL v4.0.1 §5.5",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
        "original_report": bug.model_dump(),
        "score_result": {
            "bug_id": score_result.bug_id,
            "total_score": score_result.total_score,
            "grade": score_result.grade,
            "breakdown": score_result.breakdown.as_dict(),
            "alerts": [a.model_dump() for a in score_result.alerts],
            "scored_at": score_result.scored_at,
        },
        "rewritten_report": rewritten.model_dump(),
    }


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> Tuple[str, str]:
    with st.sidebar:
        st.markdown("## 🔧 Configuration")

        st.markdown("### Input Mode")
        input_mode = st.radio(
            "input_mode_radio",
            options=["📋 Select Sample Bug", "✏️ Paste Custom Text"],
            label_visibility="collapsed",
        )

        st.markdown("---")

        # ── Rewrite Mode Selector ─────────────────────────────────────────
        st.markdown("### 🤖 Rewrite Engine")

        _groq_key   = bool(os.getenv("GROQ_API_KEY", "").strip())
        _openai_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
        _has_ai_key = _groq_key or _openai_key

        # If no API key is available: force Rule-Based and disable the radio
        _ui_choice = st.radio(
            "rewrite_mode_radio",
            options=["🤖 AI Rewrite", "⚙️ Rule-Based"],
            label_visibility="collapsed",
            index=0 if _has_ai_key else 1,
            disabled=not _has_ai_key,
        )

        # Map UI choice → internal mode
        rewrite_mode = "🚀 Auto-Detect" if _ui_choice == "🤖 AI Rewrite" else "⚙️ Rule-Based"

        # Status badges (shown only in AI mode)
        if _has_ai_key and _ui_choice == "🤖 AI Rewrite":
            def _badge(label, color, icon):
                return (f'<span style="background:rgba({color},0.12);border:1px solid '
                        f'rgba({color},0.35);color:rgb({color});border-radius:12px;'
                        f'padding:0.15rem 0.55rem;font-size:0.73rem;font-weight:600;">'
                        f'{icon} {label}</span>')

            groq_badge   = _badge("Ready","52,211,153","✓") if _groq_key   else _badge("No Key","248,81,73","✗")
            # openai_badge = _badge("Ready","52,211,153","✓") if _openai_key else _badge("No Key","248,81,73","✗")

            st.markdown(f"""
            <div style="font-size:0.78rem;line-height:2.2;color:#8b949e;margin-top:0.4rem;">
              🤖 &nbsp;&nbsp;GPT-4o Open AI&nbsp;&nbsp;&nbsp;&nbsp;{groq_badge}<br>
              
            </div>
            """, unsafe_allow_html=True)

        if not _has_ai_key:
            st.warning("⚠️ No AI key found — will use Rule-Based fallback.")

        st.markdown("---")
        st.markdown("### 📊 Scoring Weights")
        st.markdown("""
        <div class="sidebar-metric">
          <div class="sidebar-metric-label">Structural Completeness</div>
          <div class="sidebar-metric-value">40 pts</div>
        </div>
        <div class="sidebar-metric">
          <div class="sidebar-metric-label">Reproducibility</div>
          <div class="sidebar-metric-value">35 pts</div>
        </div>
        <div class="sidebar-metric">
          <div class="sidebar-metric-label">Clarity & Context</div>
          <div class="sidebar-metric-value">25 pts</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🏅 Grade Scale")
        st.markdown("""
        <div style="font-size:0.82rem; color:#c9d1d9; line-height:2;">
          🏆 <b style='color:#34d399;'>Excellent</b> — ≥ 80<br>
          ✅ <b style='color:#58a6ff;'>Good</b> — 60–79<br>
          ⚠️ <b style='color:#f59e0b;'>Needs Improvement</b> — 40–59<br>
          ❌ <b style='color:#f85149;'>Poor</b> — &lt; 40
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(
            "<div style='font-size:0.72rem; color:#6e7681; text-align:center;'>"
            "ISTQB CTFL v4.0.1 §5.5 · IGS Hackathon 2026</div>",
            unsafe_allow_html=True
        )

    return input_mode, rewrite_mode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    render_hero()
    input_mode, rewrite_mode = render_sidebar()

    bug: Optional[BugReport] = None

    # ── Input Panel ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📥 Bug Report Input</div>',
                unsafe_allow_html=True)

    if input_mode == "📋 Select Sample Bug":
        if not SAMPLE_BUGS:
            st.error("Sample bugs not found. Ensure `data/sample_bugs.json` exists.")
            return

        labels = [b.get("label", b.get("id", f"Bug {i}")) for i, b in enumerate(SAMPLE_BUGS)]
        selected_label = st.selectbox(
            "Choose a sample bug report:",
            options=labels,
            index=4,  # Default to a "Poor" report so improvements are visible
            help="Bugs are labelled ✅ Complete, ⚠️ Borderline, or ❌ Poor for easy comparison."
        )
        selected_idx = labels.index(selected_label)
        bug_data = SAMPLE_BUGS[selected_idx]

        with st.expander("📄 View raw JSON", expanded=False):
            st.code(json.dumps(bug_data, indent=2), language="json")

        try:
            bug = parse_bug_from_dict(bug_data)
        except Exception as e:
            st.error(f"Failed to parse sample bug: {e}")
            return

    else:  # Custom text
        placeholder = """Summary: Search results take too long to load

Description: The search feature is very slow sometimes.

Steps to reproduce:
1. Login to the app
2. Click search
3. Type something

Expected result: Results should be fast

Actual result: Very slow

Severity: High
Priority: P2"""

        custom_text = st.text_area(
            "Paste your bug report (free-form, structured, or JSON):",
            value=placeholder,
            height=280,
            help=(
                "Accepted formats:\n"
                "• Free-form text with labelled sections (see format guide below)\n"
                "• JSON object with fields: id, summary, description, "
                "steps_to_reproduce, expected_result, actual_result, "
                "environment, severity, priority"
            )
        )

        # ── Format convention guide ───────────────────────────────────────────
        with st.expander("📋 Input format guide", expanded=False):
            st.markdown("""
**Recognised field names** (case-insensitive):

| Field | Accepted labels |
|---|---|
| Summary | `Summary`, `Title`, `Headline` |
| Description | `Description`, `Details`, `Body` |
| Steps | `Steps to Reproduce`, `Steps`, `Reproduction Steps`, `How to Reproduce` |
| Expected | `Expected Result`, `Expected`, `Expected Behavior` |
| Actual | `Actual Result`, `Actual`, `Actual Behavior`, `Observed` |
| Environment | `Environment`, `Env` |
| Severity | `Severity` |
| Priority | `Priority` |

**Three ways to write each field — all work:**

```
# Option 1 — field and value on the same line (colon required)
Summary: Search results take too long to load

# Option 2 — field name alone on its own line, content below
Summary:
Search results take too long to load

# Option 3 — bare keyword on its own line (colon optional)
Summary
Search results take too long to load
```

> **Tip:** For multi-line content (like Steps), use one step per line. \
> JSON input is also accepted — paste the full object and it is detected automatically.
            """)
        custom_id = st.text_input(
            "Bug ID (used only when JSON has no id field):", value="CUSTOM-001", max_chars=30
        )

        if not custom_text.strip():
            st.info("Enter a bug report above to analyse it.")
            return

        # Show a hint when the user appears to have pasted JSON
        stripped = custom_text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed_json = json.loads(stripped)
                if isinstance(parsed_json, dict) and "original_report" in parsed_json:
                    st.success(
                        "✅ Export payload detected — extracting `original_report` "
                        "and re-analysing it fresh."
                    )
                else:
                    st.success("✅ Valid JSON detected — parsing as structured bug report.")
            except json.JSONDecodeError:
                st.warning("⚠️ Input looks like JSON but is not valid. Check for syntax errors.")

        try:
            bug = parse_bug_from_text(custom_text, bug_id=custom_id)
        except Exception as e:
            st.error(f"Failed to parse custom report: {e}")
            return

        # Show parsed fields so user can verify extraction
        with st.expander("🔍 Parsed fields preview (verify before analysing)", expanded=False):
            st.code(json.dumps({
                "id": bug.id,
                "summary": bug.summary or "(empty)",
                "description": bug.description or "(empty)",
                "steps_to_reproduce": bug.steps_to_reproduce or [],
                "expected_result": bug.expected_result or "(empty)",
                "actual_result": bug.actual_result or "(empty)",
                "environment": (
                    bug.environment.model_dump(exclude_none=True)
                    if hasattr(bug.environment, "model_dump")
                    else bug.environment
                ),
                "severity": bug.severity or "(empty)",
                "priority": bug.priority or "(empty)",
            }, indent=2), language="json")

    # ── Action Button ─────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_btn, _ = st.columns([1, 3])
    with col_btn:
        analyse_clicked = st.button(
            "🔍 Analyse & Rewrite",
            type="primary",
            use_container_width=True,
        )

    if not analyse_clicked:
        st.markdown(
            "<div style='color:#6e7681; font-size:0.85rem; margin-top:0.5rem;'>"
            "👆 Select a bug report and click <b>Analyse &amp; Rewrite</b> to begin.</div>",
            unsafe_allow_html=True
        )
        return

    # ── Processing ────────────────────────────────────────────────────────────
    with st.spinner("🔄 Scoring and rewriting report…"):
        score_result: ScoreResult = score_bug_report(bug)
        rewritten: RewrittenBug = rewrite_bug_report(bug, mode=rewrite_mode)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Output 1 : Quality Score ──────────────────────────────────────────────
    st.markdown('<div class="section-header">📊 Output 1 — Quality Score</div>',
                unsafe_allow_html=True)

    col_grade, col_struct, col_repro, col_clarity = st.columns([1.5, 1, 1, 1])

    with col_grade:
        render_grade(score_result.total_score, score_result.grade)

    with col_struct:
        render_score_card(
            "Structural Completeness",
            score_result.breakdown.structural_completeness,
            40.0,
            "#58a6ff",
            "linear-gradient(90deg, #1f6feb, #58a6ff)",
        )

    with col_repro:
        render_score_card(
            "Reproducibility",
            score_result.breakdown.reproducibility,
            35.0,
            "#a78bfa",
            "linear-gradient(90deg, #7c3aed, #a78bfa)",
        )

    with col_clarity:
        render_score_card(
            "Clarity & Context",
            score_result.breakdown.clarity_context,
            25.0,
            "#34d399",
            "linear-gradient(90deg, #059669, #34d399)",
        )

    # ── Output 2 : Alerts ─────────────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">🚨 Output 2 — Missing-Field & Ambiguity Alerts</div>',
                unsafe_allow_html=True)

    render_alerts(score_result)

    # ── Output 3 : Rewritten Report Comparison ────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">✨ Output 3 — ISTQB-Formatted Rewrite</div>',
                unsafe_allow_html=True)

    render_comparison(bug, rewritten)

    # ── JSON Export ───────────────────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">📤 Export Triage Evaluation</div>',
                unsafe_allow_html=True)

    export_payload = build_export_payload(bug, score_result, rewritten)
    export_json = json.dumps(export_payload, indent=2, default=str)

    col_dl, col_preview = st.columns([1, 3])
    with col_dl:
        filename = f"triage_{bug.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        st.download_button(
            label="⬇️ Download JSON",
            data=export_json,
            file_name=filename,
            mime="application/json",
            use_container_width=True,
        )
    with col_preview:
        with st.expander("👁️ Preview JSON payload"):
            st.code(export_json, language="json")

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center; color:#484f58; font-size:0.75rem; "
        "border-top: 1px solid #21262d; padding-top:1rem;'>"
        "Bug Report Quality Assistant · ISTQB CTFL v4.0.1 §5.5 · "
        "IGS Engineering Quality Fresher Hackathon 2026 · "
        "Built with Streamlit &amp; Pydantic v2"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
