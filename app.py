"""
app.py — V3 Streamlit Dashboard with auth, alert review queue,
correlation view, and analyst workflow features.
"""

import html
import json
import os
import uuid

import pandas as pd
import streamlit as st

from auth import streamlit_auth_gate
from config_loader import load_secrets, get_config
from db import (
    DB_PATH,
    clear_all_snapshots,
    count_events_by_event_type,
    count_snapshots,
    delete_events_by_event_type,
    get_all_events,
    get_failed_extractions,
    get_all_runs,
    get_all_alerts,
    get_all_correlations,
    get_unreviewed_events,
    save_review,
    update_event_review,
)
from schema import AnalystReview
from viz_utils import (
    build_run_history_df,
    compute_week_over_week_deltas,
    confidence_chart,
    confidence_summary_stats,
    daily_competitor_nunique,
    daily_series,
    sparkline_chart,
    timeline_chart_for_df,
    timeline_summary_stats,
)

HIGH_CONFIDENCE_THRESHOLD = 0.7
HIGH_BADGE_THRESHOLD = 0.8
MEDIUM_BADGE_THRESHOLD = 0.5


def format_date_label(value):
    """Return a readable YYYY-MM-DD label for dashboard display."""
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        text = str(value).strip()
        return text[:10] if text else "Unknown"
    return parsed.strftime("%Y-%m-%d")


def safe_value(value, fallback="—"):
    """Normalize missing values before display."""
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def get_confidence_badge(score):
    """Return HTML badge markup for the signal confidence band."""
    if score > HIGH_BADGE_THRESHOLD:
        return '<span class="badge badge-high">HIGH</span>'
    if score > MEDIUM_BADGE_THRESHOLD:
        return '<span class="badge badge-med">MEDIUM</span>'
    return '<span class="badge badge-low">LOW</span>'


def render_section_header(label, title, caption):
    """Render a reusable section heading block."""
    header_html = "\n".join([
        '<div class="section-header">',
        f'<div class="section-label">{html.escape(label)}</div>',
        f'<div class="section-title">{html.escape(title)}</div>',
        f'<div class="section-caption">{html.escape(caption)}</div>',
        "</div>",
    ])
    st.markdown(header_html, unsafe_allow_html=True)


def render_empty_state(title, message, tips):
    """Render a friendly empty state for low or zero-data views."""
    tips_html = "".join(f"<li>{html.escape(tip)}</li>" for tip in tips)
    block_html = "\n".join([
        '<div class="empty-state">',
        f'<div class="empty-state-title">{html.escape(title)}</div>',
        f'<div class="empty-state-text">{html.escape(message)}</div>',
        f'<ul class="empty-state-list">{tips_html}</ul>',
        "</div>",
    ])
    st.markdown(block_html, unsafe_allow_html=True)


def render_signal_card(row):
    """Render one signal card in the feed.

    The card is built as a single HTML block with **no leading whitespace**
    (avoids Markdown interpreting it as an indented code-block) and **no
    blank lines** (avoids prematurely ending the HTML block in CommonMark).
    """
    score_value = row.get("confidence_score", 0.0)
    score = 0.0 if pd.isna(score_value) else float(score_value)
    is_new_value = row.get("is_new", 0)
    is_new = 0 if pd.isna(is_new_value) else int(is_new_value)

    title = html.escape(safe_value(row.get("title"), "Untitled signal"))
    competitor = html.escape(safe_value(row.get("competitor"), "Unknown competitor"))
    event_type = html.escape(safe_value(row.get("event_type"), "Unknown type"))
    signal_label = html.escape(safe_value(row.get("signal_type"), "Not classified"))
    date_label = html.escape(format_date_label(row.get("date_detected", "")))
    description = html.escape(safe_value(row.get("description"), "No description provided."))
    implication = html.escape(
        safe_value(row.get("strategic_implication"), "No strategic implication provided.")
    )
    source_url = html.escape(safe_value(row.get("source_url"), "#"), quote=True)
    content_hash = safe_value(row.get("content_hash"), "—")
    content_hash = content_hash[:16] + "..." if content_hash != "—" else content_hash

    review_status = safe_value(row.get("review_status"), "unreviewed")
    correlation_id = safe_value(row.get("correlation_id"), "")

    new_badge = '<span class="badge badge-new">NEW</span>' if is_new else ""
    review_badge = ""
    if review_status == "confirmed":
        review_badge = '<span class="badge" style="background:#22c55e;">CONFIRMED</span>'
    elif review_status == "dismissed":
        review_badge = '<span class="badge" style="background:#6b7280;">DISMISSED</span>'
    elif review_status == "escalated":
        review_badge = '<span class="badge" style="background:#f59e0b;">ESCALATED</span>'

    corr_tag = ""
    if correlation_id and correlation_id != "—":
        corr_tag = '<span class="badge" style="background:#8b5cf6;">CORRELATED</span>'

    badges = " ".join(filter(None, [get_confidence_badge(score), new_badge, review_badge, corr_tag]))

    details = html.escape(
        json.dumps(
            {
                "event_id": safe_value(row.get("event_id"), "—"),
                "confidence_score": round(score, 2),
                "run_id": safe_value(row.get("run_id"), "—"),
                "content_hash": content_hash,
                "review_status": review_status,
                "correlation_id": correlation_id if correlation_id != "—" else "",
                "provenance": safe_value(row.get("provenance"), "pipeline"),
            },
            indent=2,
        )
    )

    card_html = "\n".join([
        '<div class="feed-card">',
        f'<div class="feed-card-badges">{badges}</div>',
        f'<div class="feed-card-title">{title}</div>',
        '<div class="feed-card-implication">',
        "<strong>Strategic implication for ABB</strong><br>",
        f"<em>{implication}</em>",
        "</div>",
        '<div class="feed-card-meta">',
        f"<span><strong>Competitor:</strong> {competitor}</span>",
        f"<span><strong>Type:</strong> {event_type}</span>",
        f"<span><strong>Signal:</strong> {signal_label}</span>",
        f"<span><strong>Detected:</strong> {date_label}</span>",
        f'<span><a href="{source_url}" target="_blank" rel="noopener noreferrer">Source</a></span>',
        "</div>",
        '<details class="feed-details">',
        "<summary>Evidence and technical details</summary>",
        '<div class="feed-card-copy-secondary">',
        f"<p><strong>What happened:</strong> {description}</p>",
        "</div>",
        f"<pre>{details}</pre>",
        "</details>",
        "</div>",
    ])
    st.markdown(card_html, unsafe_allow_html=True)


def _feed_sort_column_options(df_columns):
    """Labels for primary/secondary sort (only columns that exist)."""
    opts = ["Date detected", "Confidence", "Competitor", "Event type", "Title"]
    if "signal_type" in df_columns:
        opts.insert(4, "Signal type")
    return opts


def _feed_label_to_sort_col(label, df_work):
    """Map UI label to a column name present on df_work (may add _sort_dt)."""
    if label == "Date detected":
        if "_sort_dt" not in df_work.columns:
            df_work["_sort_dt"] = pd.to_datetime(df_work["date_detected"], errors="coerce")
        return "_sort_dt"
    mapping = {
        "Confidence": "confidence_score",
        "Competitor": "competitor",
        "Event type": "event_type",
        "Signal type": "signal_type",
        "Title": "title",
    }
    col = mapping.get(label)
    if col and col in df_work.columns:
        if df_work[col].dtype == object or str(df_work[col].dtype) == "string":
            df_work[col] = df_work[col].fillna("").astype(str)
        return col
    return None


def apply_feed_filters_and_sort(source_df):
    """Apply feed-only filters and sort; returns a copy (empty allowed)."""
    out = source_df.copy()
    if out.empty:
        return out

    if st.session_state.get("feed_new_only"):
        is_new = out["is_new"].fillna(0)
        try:
            mask = is_new.astype(int) == 1
        except (ValueError, TypeError):
            mask = is_new.astype(bool)
        out = out[mask]

    if st.session_state.get("feed_high_only") and "confidence_score" in out.columns:
        out = out[out["confidence_score"] > HIGH_CONFIDENCE_THRESHOLD]

    if "signal_type" in out.columns:
        sel_st = st.session_state.get("feed_signal_types") or []
        if sel_st:
            out = out[out["signal_type"].isin(sel_st)]

    q = (st.session_state.get("feed_search") or "").strip().lower()
    if q:
        for col in ("title", "description", "strategic_implication"):
            if col not in out.columns:
                out[col] = ""
        m = (
            out["title"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
            | out["description"].fillna("").astype(str).str.lower().str.contains(q, regex=False)
            | out["strategic_implication"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(q, regex=False)
        )
        out = out[m]

    if out.empty:
        return out

    primary = st.session_state.get("feed_sort_primary", "Date detected")
    secondary = st.session_state.get("feed_sort_secondary", "(none)")
    ascending = st.session_state.get("feed_sort_order", "Descending") == "Ascending"

    sort_cols = []
    seen = set()

    def _add_col(label):
        if not label or label == "(none)":
            return
        c = _feed_label_to_sort_col(label, out)
        if c and c not in seen:
            sort_cols.append(c)
            seen.add(c)

    _add_col(primary)
    if secondary != "(none)" and secondary != primary:
        _add_col(secondary)

    if not sort_cols:
        if "_sort_dt" not in out.columns:
            out["_sort_dt"] = pd.to_datetime(out["date_detected"], errors="coerce")
        sort_cols = ["_sort_dt"]

    asc_list = [ascending] * len(sort_cols)
    out = out.sort_values(by=sort_cols, ascending=asc_list, na_position="last")
    out = out.drop(columns=[c for c in ("_sort_dt",) if c in out.columns], errors="ignore")
    return out


# ───────────────────────────────────────────────────────────────
# Page config & theme
# ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="RivalSense — V3",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_secrets()
config = get_config()

# Auth gate
streamlit_auth_gate(config.auth)

# Dark-mode-friendly custom CSS
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        .main .block-container {
            max-width: 1350px;
        }
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(0, 119, 182, 0.18), transparent 25%),
                radial-gradient(circle at top left, rgba(76, 201, 240, 0.08), transparent 20%);
        }
        [data-testid="stSidebarContent"] {
            background: linear-gradient(180deg, rgba(17, 24, 39, 0.98), rgba(11, 16, 26, 0.98));
        }
        .sidebar-note {
            padding: 0.95rem 1rem;
            margin-bottom: 1rem;
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.18);
            background: rgba(15, 23, 42, 0.65);
            color: #dbe4f0;
            line-height: 1.55;
        }
        .sidebar-note code {
            color: #8ed8ff;
        }
        .hero-banner {
            padding: 1.6rem 1.75rem;
            border-radius: 24px;
            border: 1px solid rgba(125, 211, 252, 0.22);
            background: linear-gradient(135deg, rgba(11, 25, 45, 0.96), rgba(18, 48, 78, 0.88));
            box-shadow: 0 18px 50px rgba(15, 23, 42, 0.28);
            margin-bottom: 1rem;
        }
        .hero-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.74rem;
            font-weight: 700;
            color: #8ed8ff;
            margin-bottom: 0.65rem;
        }
        .hero-title {
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.15;
            margin: 0;
            color: #f8fbff;
        }
        .hero-subtitle {
            margin-top: 0.7rem;
            color: #cfdef0;
            font-size: 1rem;
            line-height: 1.65;
        }
        .hero-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1rem;
        }
        .hero-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            border-radius: 999px;
            padding: 0.4rem 0.8rem;
            background: rgba(148, 163, 184, 0.14);
            border: 1px solid rgba(191, 219, 254, 0.16);
            color: #ecf5ff;
            font-size: 0.84rem;
        }
        .summary-panel {
            padding: 1.3rem 1.2rem;
            border-radius: 22px;
            border: 1px solid rgba(148, 163, 184, 0.18);
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.84), rgba(17, 24, 39, 0.7));
            min-height: 100%;
        }
        .summary-eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.72rem;
            color: #8ed8ff;
            margin-bottom: 0.7rem;
            font-weight: 700;
        }
        .summary-value {
            font-size: 1.9rem;
            font-weight: 700;
            color: #f8fbff;
            margin-bottom: 0.2rem;
        }
        .summary-caption {
            color: #c5d4e8;
            margin-bottom: 1rem;
        }
        .summary-list {
            display: grid;
            gap: 0.7rem;
        }
        .summary-item {
            padding-top: 0.7rem;
            border-top: 1px solid rgba(148, 163, 184, 0.16);
        }
        .summary-label {
            color: #8fa7c3;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 0.2rem;
        }
        .summary-text {
            color: #f6fbff;
            font-size: 0.95rem;
        }
        .section-header {
            margin-top: 1.4rem;
            margin-bottom: 1rem;
        }
        .section-label {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #8ed8ff;
            font-size: 0.74rem;
            font-weight: 700;
            margin-bottom: 0.3rem;
        }
        .section-title {
            font-size: 1.35rem;
            font-weight: 700;
            color: #f8fbff;
            margin-bottom: 0.2rem;
        }
        .section-caption {
            color: #9eb0c6;
            line-height: 1.55;
        }
        div[data-testid="stMetric"] {
            padding: 1rem 1.1rem;
            border-radius: 18px;
            border: 1px solid rgba(148, 163, 184, 0.18);
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.88), rgba(15, 23, 42, 0.64));
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
        }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] p,
        div[data-testid="stMetric"] [data-testid="stMarkdownContainer"] p {
            color: #cbd5e1 !important;
        }
        div[data-testid="stMetricLabel"],
        div[data-testid="stMetricLabel"] p {
            color: #94a3b8 !important;
            font-weight: 600;
            font-size: 0.82rem !important;
        }
        div[data-testid="stMetricValue"],
        div[data-testid="stMetricValue"] p {
            color: #f8fbff !important;
            font-weight: 700;
        }
        div[data-testid="stMetricDelta"] {
            color: #94a3b8;
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] {
            background-color: rgba(51, 65, 85, 0.95) !important;
            border-color: rgba(148, 163, 184, 0.35) !important;
        }
        [data-testid="stMultiSelect"] [data-baseweb="tag"] span {
            color: #e2e8f0 !important;
        }
        .chart-note {
            color: #9eb0c6;
            margin-top: -0.15rem;
            margin-bottom: 0.75rem;
            line-height: 1.5;
        }
        .badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.28rem 0.75rem;
            border-radius: 999px;
            font-size: 0.74rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            color: #ffffff;
        }
        .badge-new {
            background: linear-gradient(135deg, #00b4d8, #0077b6);
        }
        .badge-high {
            background: linear-gradient(135deg, #ef4444, #dc2626);
        }
        .badge-med {
            background: linear-gradient(135deg, #f59e0b, #ea580c);
        }
        .badge-low {
            background: linear-gradient(135deg, #3b82f6, #1d4ed8);
        }
        .feed-card {
            max-width: 980px;
            margin-left: auto;
            margin-right: auto;
            padding: 1.2rem 1.25rem;
            margin-bottom: 1rem;
            border-radius: 22px;
            border: 1px solid rgba(148, 163, 184, 0.18);
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.84), rgba(17, 24, 39, 0.72));
            box-shadow: 0 16px 40px rgba(2, 6, 23, 0.12);
        }
        .feed-card-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-bottom: 0.8rem;
        }
        .feed-card-title {
            color: #f8fbff;
            font-size: 1.28rem;
            font-weight: 700;
            line-height: 1.45;
            margin-bottom: 0.65rem;
        }
        .feed-card-implication {
            font-size: 1.05rem;
            line-height: 1.6;
            color: #e8f1fc;
            margin-bottom: 1rem;
            max-width: 70ch;
        }
        .feed-card-implication strong {
            color: #f1f5f9;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .feed-card-implication em {
            color: #bae6fd;
            font-style: normal;
            font-weight: 500;
        }
        .feed-card-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem 1rem;
            color: #9eb0c6;
            font-size: 0.9rem;
            line-height: 1.6;
            margin-bottom: 0.95rem;
        }
        .feed-card-meta strong {
            color: #dce8f5;
        }
        .feed-card-meta a {
            color: #8ed8ff;
            text-decoration: none;
            font-weight: 600;
        }
        .feed-card-copy-secondary p {
            margin: 0.45rem 0;
            color: #94a3b8;
            line-height: 1.65;
            max-width: 70ch;
            font-size: 0.92rem;
        }
        .feed-card-copy-secondary strong {
            color: #cbd5e1;
        }
        .feed-details {
            margin-top: 0.95rem;
            padding-top: 0.85rem;
            border-top: 1px solid rgba(148, 163, 184, 0.14);
        }
        .feed-details summary {
            cursor: pointer;
            color: #8ed8ff;
            font-weight: 600;
        }
        .feed-details pre {
            margin-top: 0.75rem;
            padding: 0.85rem;
            border-radius: 14px;
            background: rgba(15, 23, 42, 0.75);
            color: #d8e5f3;
            white-space: pre-wrap;
            word-break: break-word;
            font-size: 0.84rem;
            line-height: 1.55;
        }
        .empty-state {
            padding: 2rem 1.5rem;
            border-radius: 22px;
            border: 1px dashed rgba(148, 163, 184, 0.28);
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.68), rgba(15, 23, 42, 0.46));
            text-align: center;
            margin-top: 0.75rem;
        }
        .empty-state-title {
            font-size: 1.2rem;
            font-weight: 700;
            color: #f8fbff;
            margin-bottom: 0.55rem;
        }
        .empty-state-text {
            max-width: 700px;
            margin: 0 auto 0.9rem auto;
            color: #b7c8dc;
            line-height: 1.65;
        }
        .empty-state-list {
            display: inline-block;
            text-align: left;
            margin: 0;
            padding-left: 1.15rem;
            color: #dbe7f3;
            line-height: 1.75;
        }
        hr {
            border-color: rgba(148, 163, 184, 0.16);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

if not os.environ.get("GOOGLE_API_KEY"):
    st.warning(
        "GOOGLE_API_KEY is not set. The extraction pipeline will emit MOCK_SIGNAL "
        "placeholders instead of Gemini analysis. Add your key to `prototype/.env` "
        "(copy from `.env.example`) or set the variable before running `python main.py`."
    )

# ───────────────────────────────────────────────────────────────
# Navigation tabs
# ───────────────────────────────────────────────────────────────

tab_radar, tab_review, tab_correlations, tab_ops = st.tabs(
    ["Radar", "Review Queue", "Correlations", "Operations"]
)

# ───────────────────────────────────────────────────────────────
# Sidebar: filters & controls
# ───────────────────────────────────────────────────────────────

st.sidebar.header("Controls")

events_raw = get_all_events()

if not events_raw:
    with tab_radar:
        hero_html = "\n".join([
            '<div class="hero-banner">',
            '<div class="hero-kicker">Competitive Intelligence</div>',
            '<h1 class="hero-title">RivalSense &mdash; Early-Warning Radar</h1>',
            '<div class="hero-subtitle">',
            "Monitor weak signals across competitors, track momentum shifts,",
            "and surface evidence that may matter to ABB.",
            "</div>",
            "</div>",
        ])
        st.markdown(hero_html, unsafe_allow_html=True)
        empty_tips = [
            "Run python main.py to collect and extract events.",
            "Refresh the page after the pipeline finishes.",
            "Use scheduler.py later if you want recurring updates.",
        ]
        if not os.environ.get("GOOGLE_API_KEY"):
            empty_tips.insert(
                0,
                "Set GOOGLE_API_KEY in .env (see .env.example) for real LLM extraction; "
                "without it, the pipeline only stores mock signals.",
            )
        render_empty_state(
            "No intelligence events found yet",
            "The dashboard is ready, but there is no stored signal data to visualize. "
            "Run the collection pipeline once to populate the feed and charts.",
            empty_tips,
        )
    st.stop()

full_df = pd.DataFrame(events_raw)
df = full_df.copy()

if "is_new" not in full_df.columns:
    full_df["is_new"] = 1
if "is_new" not in df.columns:
    df["is_new"] = 1

competitors_available = sorted(full_df["competitor"].dropna().unique().tolist())
signal_types = (
    sorted(full_df["signal_type"].dropna().unique().tolist())
    if "signal_type" in full_df.columns
    else []
)

if "radar_competitors" not in st.session_state:
    st.session_state.radar_competitors = list(competitors_available)
if "radar_signals" not in st.session_state:
    st.session_state.radar_signals = list(signal_types)
if "radar_min_conf" not in st.session_state:
    st.session_state.radar_min_conf = 0.0

alerts_label = "enabled" if config.alerts.enabled else "disabled"
sidebar_html = "\n".join([
    '<div class="sidebar-note">',
    "<strong>RivalSense V3</strong><br>",
    "<code>python main.py</code> &middot; <code>python scheduler.py</code><br>",
    f'<span style="opacity:0.88">Alerts: <code>{html.escape(alerts_label)}</code>',
    f'&middot; Auth: <code>{html.escape(config.auth.provider)}</code></span>',
    "</div>",
])
st.sidebar.markdown(sidebar_html, unsafe_allow_html=True)

with st.sidebar.expander("Pipeline maintenance", expanded=False):
    n_snap = count_snapshots()
    n_mock = count_events_by_event_type("MOCK_SIGNAL")
    st.caption(f"Snapshots: **{n_snap}** · DB `{DB_PATH}`")
    st.caption(
        "Clear snapshots so the next run treats every URL as changed and runs "
        "extraction again (useful after adding GOOGLE_API_KEY)."
    )
    if st.button("Clear all snapshots", width="stretch", key="clear_snapshots_btn"):
        removed = clear_all_snapshots()
        st.success(f"Removed {removed} snapshot(s). Run `python main.py` to re-extract.")
    st.caption(
        f"Placeholder rows (**{n_mock}** `MOCK_SIGNAL`) stay in the database from earlier "
        "runs without a key. Remove them after your key works so the feed matches live analysis."
    )
    if st.button(
        "Remove MOCK_SIGNAL events",
        width="stretch",
        key="delete_mock_events_btn",
    ):
        deleted = delete_events_by_event_type("MOCK_SIGNAL")
        st.success(f"Deleted {deleted} mock placeholder event(s). Refresh the page.")

with st.sidebar.expander("Filters", expanded=False):
    competitor_filter = st.multiselect(
        "Competitors",
        options=competitors_available,
        key="radar_competitors",
    )
    if signal_types:
        signal_filter = st.multiselect(
            "Signal types",
            options=signal_types,
            key="radar_signals",
        )
    else:
        signal_filter = []
    min_confidence = st.slider(
        "Min confidence",
        0.0,
        1.0,
        key="radar_min_conf",
        step=0.05,
    )
    if st.button("Reset filters", width="stretch", key="radar_reset_filters"):
        st.session_state.radar_competitors = list(competitors_available)
        st.session_state.radar_signals = list(signal_types)
        st.session_state.radar_min_conf = 0.0
        st.rerun()

if signal_types:
    df = df[df["signal_type"].isin(signal_filter)]

df = df[df["competitor"].isin(competitor_filter)]
df = df[df["confidence_score"] >= min_confidence]

n_sig_types = len(signal_types) if signal_types else 0
st.sidebar.caption(
    f"{len(competitor_filter)} competitors · "
    f"{len(signal_filter)} of {n_sig_types} signal types · "
    f"min conf {min_confidence:.2f}"
)

selected_competitors_label = (
    "All competitors"
    if len(competitor_filter) == len(competitors_available)
    else f"{len(competitor_filter)} selected"
)
selected_signal_label = "All signal types"
if signal_types:
    selected_signal_label = (
        "All signal types"
        if len(signal_filter) == len(signal_types)
        else f"{len(signal_filter)} selected"
    )

show_run_history = st.sidebar.checkbox("Show run history", value=False, key="radar_show_runs")
if show_run_history:
    rh_df = build_run_history_df(full_df, limit=10)
    if not rh_df.empty:
        st.sidebar.subheader("Run history")
        st.sidebar.dataframe(
            rh_df,
            height=220,
            hide_index=True,
            width="stretch",
        )

failed = get_failed_extractions()
if failed:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Failed extractions")
    st.sidebar.caption(f"{len(failed)} failed")
    with st.sidebar.expander("View failures"):
        for failure in failed[:5]:
            cat = failure.get("failure_category") or "unknown"
            http_code = failure.get("http_status_code")
            http_part = f" HTTP {http_code}" if http_code is not None else ""
            msg = (failure.get("error_message") or "")[:120]
            st.sidebar.text(f"{failure['url']}\n[{cat}{http_part}] {msg}")


# ═══════════════════════════════════════════════════════════════
# TAB: RADAR (main intelligence view)
# ═══════════════════════════════════════════════════════════════

with tab_radar:
    filtered_count = len(df)
    total_count = len(full_df)
    new_count = int(df["is_new"].sum()) if "is_new" in df.columns else 0
    high_confidence_count = len(df[df["confidence_score"] > HIGH_CONFIDENCE_THRESHOLD])
    competitor_count = len(df["competitor"].unique()) if filtered_count > 0 else 0
    avg_confidence = f"{df['confidence_score'].mean():.2f}" if filtered_count > 0 else "0.00"
    latest_detected = "Unknown"
    if filtered_count > 0 and "date_detected" in df.columns:
        latest_date = pd.to_datetime(df["date_detected"], errors="coerce").max()
        if pd.notna(latest_date):
            latest_detected = latest_date.strftime("%Y-%m-%d")

    hero_col, summary_col = st.columns([2.2, 1])

    with hero_col:
        hero_html = "\n".join([
            '<div class="hero-banner">',
            '<div class="hero-kicker">Competitive Intelligence Dashboard</div>',
            '<h1 class="hero-title">RivalSense &mdash; Early-Warning Radar</h1>',
            '<div class="hero-subtitle">',
            "Scan emerging competitor activity, compare weak signals across sources,",
            "and focus on the stories most worth analyst attention.",
            "</div>",
            '<div class="hero-chip-row">',
            f'<span class="hero-chip">{total_count} total stored signals</span>',
            f'<span class="hero-chip">{html.escape(selected_competitors_label)}</span>',
            f'<span class="hero-chip">{html.escape(selected_signal_label)}</span>',
            f'<span class="hero-chip">Min confidence {min_confidence:.2f}</span>',
            "</div>",
            "</div>",
        ])
        st.markdown(hero_html, unsafe_allow_html=True)

    with summary_col:
        summary_html = "\n".join([
            '<div class="summary-panel">',
            '<div class="summary-eyebrow">Current view</div>',
            f'<div class="summary-value">{filtered_count}</div>',
            '<div class="summary-caption">signals match the active filters</div>',
            '<div class="summary-list">',
            '<div class="summary-item">',
            '<div class="summary-label">Average confidence</div>',
            f'<div class="summary-text">{avg_confidence}</div>',
            "</div>",
            '<div class="summary-item">',
            '<div class="summary-label">Latest detection</div>',
            f'<div class="summary-text">{html.escape(latest_detected)}</div>',
            "</div>",
            '<div class="summary-item">',
            '<div class="summary-label">Competitors represented</div>',
            f'<div class="summary-text">{competitor_count}</div>',
            "</div>",
            "</div>",
            "</div>",
        ])
        st.markdown(summary_html, unsafe_allow_html=True)

    # Metrics row
    render_section_header(
        "Overview",
        "Seven-day momentum",
        "Primary numbers reflect the full filtered view. Deltas compare the latest 7 days to the prior 7 days.",
    )

    deltas = compute_week_over_week_deltas(df)

    def _delta_for_metric(d):
        if d is None:
            return None
        if abs(d - round(d)) < 1e-9:
            return int(round(d))
        return round(d, 2)

    col1, col2, col3, col4 = st.columns(4)
    _, td = deltas["total"]
    col1.metric("Total signals", filtered_count, delta=_delta_for_metric(td))
    _, hd = deltas["high_conf"]
    col2.metric("High confidence (>0.7)", high_confidence_count, delta=_delta_for_metric(hd))
    _, nd = deltas["new"]
    col3.metric("New signals", new_count, delta=_delta_for_metric(nd))
    cv7, cd = deltas["competitors"]
    col4.metric("Competitors (last 7d)", int(cv7), delta=_delta_for_metric(cd))

    spark_total = daily_series(df, end_days=30)
    spark_high = daily_series(
        df, end_days=30,
        predicate=lambda r: float(r.get("confidence_score") or 0) > HIGH_CONFIDENCE_THRESHOLD,
    )
    spark_new = daily_series(
        df, end_days=30,
        predicate=lambda r: int(r.get("is_new") or 0) == 1,
    )
    spark_comp = daily_competitor_nunique(df, end_days=30)

    sp1, sp2, sp3, sp4 = st.columns(4)
    with sp1:
        st.caption("30d daily volume")
        st.altair_chart(sparkline_chart(spark_total), width="stretch")
    with sp2:
        st.caption("30d high-conf per day")
        st.altair_chart(sparkline_chart(spark_high), width="stretch")
    with sp3:
        st.caption("30d new per day")
        st.altair_chart(sparkline_chart(spark_new), width="stretch")
    with sp4:
        st.caption("30d distinct competitors / day")
        st.altair_chart(sparkline_chart(spark_comp), width="stretch")

    if filtered_count == 0:
        render_section_header(
            "Current view",
            "No signals match the selected filters",
            "The dashboard is working, but the current filters are too narrow for the available data.",
        )
        render_empty_state(
            "Try widening the filters",
            "There are stored events in the database, but none meet the current settings.",
            [
                "Lower the minimum confidence threshold in the sidebar.",
                "Re-select all competitors or all signal types.",
                "Run the pipeline again if you expect fresh signal coverage.",
            ],
        )
    else:
        # Charts
        render_section_header(
            "Analytics",
            "Signal trends and distribution",
            "Use these charts to understand how activity clusters over time.",
        )

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("#### Signals timeline")
            st.markdown(
                '<div class="chart-note">Bars when data is dense; markers when sparse.</div>',
                unsafe_allow_html=True,
            )
            if "date_detected" in df.columns and len(df) > 0:
                df_chart = df.copy()
                df_chart["date"] = pd.to_datetime(df_chart["date_detected"], errors="coerce").dt.date
                df_chart = df_chart.dropna(subset=["date"])
                if len(df_chart) > 0:
                    if "competitor" not in df_chart.columns:
                        df_chart["competitor"] = "—"
                    if "title" not in df_chart.columns:
                        df_chart["title"] = ""
                    timeline, timeline_note = timeline_chart_for_df(df_chart)
                    st.altair_chart(timeline, width="stretch")
                    st.caption(f"{timeline_summary_stats(df_chart)} {timeline_note}")

        with chart_col2:
            st.markdown("#### Confidence distribution")
            conf_mode = st.radio(
                "View",
                ("Histogram", "Strip plot", "Decile table"),
                horizontal=True,
                key="radar_confidence_view",
                label_visibility="collapsed",
            )
            if len(df) > 0:
                cchart = confidence_chart(df, conf_mode)
                if cchart is not None:
                    st.altair_chart(cchart, width="stretch")
                    st.caption(confidence_summary_stats(df))

        # Event feed
        render_section_header(
            "Signal feed",
            "Latest intelligence stories",
            "Each card highlights the event, source context, and strategic implication.",
        )

        all_feed_signal_types = (
            sorted(df["signal_type"].dropna().unique().tolist())
            if "signal_type" in df.columns and len(df) > 0
            else []
        )
        if "feed_signal_types" not in st.session_state:
            st.session_state.feed_signal_types = list(all_feed_signal_types)
        else:
            st.session_state.feed_signal_types = [
                x for x in st.session_state.feed_signal_types if x in all_feed_signal_types
            ]

        if "feed_sort_primary" not in st.session_state:
            st.session_state.feed_sort_primary = "Date detected"
        if "feed_sort_secondary" not in st.session_state:
            st.session_state.feed_sort_secondary = "(none)"
        if "feed_sort_order" not in st.session_state:
            st.session_state.feed_sort_order = "Descending"

        st.markdown("**Feed view**")
        _f1, _f2 = st.columns([4, 1])
        with _f1:
            st.caption("Filter and sort apply only to the list below.")
        with _f2:
            if st.button("Reset feed view", width="stretch", key="feed_reset_btn"):
                st.session_state.feed_new_only = False
                st.session_state.feed_high_only = False
                st.session_state.feed_search = ""
                st.session_state.feed_signal_types = list(all_feed_signal_types)
                st.session_state.feed_sort_primary = "Date detected"
                st.session_state.feed_sort_secondary = "(none)"
                st.session_state.feed_sort_order = "Descending"
                st.rerun()

        _row_a = st.columns((1, 1))
        with _row_a[0]:
            st.text_input("Search title / description / implication", key="feed_search", placeholder="Type to filter...")
        with _row_a[1]:
            if all_feed_signal_types:
                st.multiselect("Signal types", options=all_feed_signal_types, key="feed_signal_types")

        _row_b = st.columns((1, 1, 1, 2))
        with _row_b[0]:
            st.checkbox("New only", key="feed_new_only")
        with _row_b[1]:
            st.checkbox(f"High confidence only (>{HIGH_CONFIDENCE_THRESHOLD})", key="feed_high_only")

        sort_options = _feed_sort_column_options(df.columns)
        with _row_b[2]:
            st.selectbox("Sort by", options=sort_options, key="feed_sort_primary")
        _sec_opts = ["(none)"] + [
            o for o in sort_options if o != st.session_state.get("feed_sort_primary", "Date detected")
        ]
        if st.session_state.get("feed_sort_secondary") not in _sec_opts:
            st.session_state.feed_sort_secondary = "(none)"
        with _row_b[3]:
            _inner = st.columns((1, 1))
            with _inner[0]:
                st.selectbox("Then by", options=_sec_opts, key="feed_sort_secondary")
            with _inner[1]:
                st.radio("Order", ("Descending", "Ascending"), horizontal=True, key="feed_sort_order")

        df_feed = apply_feed_filters_and_sort(df)
        n_base = len(df)
        n_show = len(df_feed)
        if n_show != n_base or st.session_state.get("feed_search"):
            st.caption(f"Showing **{n_show}** of **{n_base}** signals in this view.")
        else:
            st.caption(f"Showing **{n_show}** signals.")

        if n_show == 0:
            render_empty_state(
                "No signals match feed filters",
                "Try clearing search text or widening event-type selection.",
                ["Click **Reset feed view** to restore defaults."],
            )
        else:
            for _, row in df_feed.iterrows():
                render_signal_card(row)


# ═══════════════════════════════════════════════════════════════
# TAB: REVIEW QUEUE
# ═══════════════════════════════════════════════════════════════

with tab_review:
    render_section_header(
        "Analyst workflow",
        "Review queue",
        "Confirm, dismiss, or escalate unreviewed signals. "
        "High-confidence events appear first.",
    )

    unreviewed = get_unreviewed_events()
    if not unreviewed:
        render_empty_state(
            "Review queue is empty",
            "All events have been reviewed, or no events exist yet.",
            ["Run the pipeline to generate new signals.", "Check the Radar tab for the full feed."],
        )
    else:
        st.caption(f"**{len(unreviewed)}** events awaiting review")
        for ev in unreviewed[:25]:
            with st.container():
                cols = st.columns([4, 1, 1, 1])
                with cols[0]:
                    score = ev.get("confidence_score", 0)
                    rev_title = html.escape(safe_value(ev.get("title"), "Untitled"))
                    rev_comp = html.escape(safe_value(ev.get("competitor"), "?"))
                    rev_sig = html.escape(safe_value(ev.get("signal_type"), "?"))
                    rev_line = (
                        f"<strong>{rev_title}</strong> &mdash; "
                        f"{rev_comp} &middot; {rev_sig} &middot; "
                        f"conf {score:.2f}"
                    )
                    st.markdown(rev_line, unsafe_allow_html=True)
                    st.caption(html.escape(safe_value(ev.get("strategic_implication"), "")[:200]))
                eid = ev.get("event_id", "")
                with cols[1]:
                    if st.button("Confirm", key=f"confirm_{eid}", width="stretch"):
                        update_event_review(eid, "confirmed")
                        save_review(AnalystReview(
                            review_id=str(uuid.uuid4())[:8],
                            event_id=eid,
                            verdict="confirmed",
                            reviewed_at=pd.Timestamp.now().isoformat(),
                        ))
                        st.rerun()
                with cols[2]:
                    if st.button("Dismiss", key=f"dismiss_{eid}", width="stretch"):
                        update_event_review(eid, "dismissed")
                        save_review(AnalystReview(
                            review_id=str(uuid.uuid4())[:8],
                            event_id=eid,
                            verdict="dismissed",
                            reviewed_at=pd.Timestamp.now().isoformat(),
                        ))
                        st.rerun()
                with cols[3]:
                    if st.button("Escalate", key=f"escalate_{eid}", width="stretch"):
                        update_event_review(eid, "escalated")
                        save_review(AnalystReview(
                            review_id=str(uuid.uuid4())[:8],
                            event_id=eid,
                            verdict="escalated",
                            reviewed_at=pd.Timestamp.now().isoformat(),
                        ))
                        st.rerun()
                st.markdown("---")


# ═══════════════════════════════════════════════════════════════
# TAB: CORRELATIONS
# ═══════════════════════════════════════════════════════════════

with tab_correlations:
    render_section_header(
        "Cross-signal analysis",
        "Correlation clusters",
        "Events that share a strategic theme across competitors or signal types.",
    )

    clusters = get_all_correlations()
    if not clusters:
        render_empty_state(
            "No correlations found yet",
            "The correlator runs after each pipeline execution. "
            "Correlations appear when multiple signals converge on a common theme.",
            [
                "Run the pipeline with multiple signal types active.",
                "Correlations require at least 2 events sharing keywords within 14 days.",
            ],
        )
    else:
        for cl in clusters[:20]:
            with st.container():
                strength = cl.get("strength", 0)
                label = html.escape(cl.get("label", "Unknown"))
                desc = html.escape(cl.get("description", ""))
                event_ids = cl.get("event_ids", [])
                competitors = [html.escape(c) for c in cl.get("competitors", [])]
                signal_types_cl = [html.escape(s) for s in cl.get("signal_types", [])]

                cl_meta = (
                    f"<strong>Strength:</strong> {strength:.2f} &middot; "
                    f"<strong>Events:</strong> {len(event_ids)} &middot; "
                    f"<strong>Competitors:</strong> {', '.join(competitors)} &middot; "
                    f"<strong>Signals:</strong> {', '.join(signal_types_cl)}"
                )
                st.markdown(f"### {label}")
                st.markdown(cl_meta, unsafe_allow_html=True)
                st.caption(desc)
                st.markdown("---")


# ═══════════════════════════════════════════════════════════════
# TAB: OPERATIONS
# ═══════════════════════════════════════════════════════════════

with tab_ops:
    render_section_header(
        "System",
        "Operations dashboard",
        "Pipeline runs, alert history, and system health.",
    )

    runs = get_all_runs()
    if runs:
        st.markdown("#### Recent pipeline runs")
        runs_df = pd.DataFrame(runs[:20])
        display_cols = [c for c in [
            "run_id", "started_at", "status", "total_urls",
            "urls_changed", "events_extracted", "alerts_sent",
            "correlations_found", "trigger",
        ] if c in runs_df.columns]
        st.dataframe(runs_df[display_cols], hide_index=True, width="stretch")
    else:
        st.caption("No pipeline runs recorded yet.")

    alerts_data = get_all_alerts()
    if alerts_data:
        st.markdown("#### Recent alerts")
        alerts_df = pd.DataFrame(alerts_data[:20])
        display_cols = [c for c in [
            "alert_id", "event_id", "channel", "status", "created_at", "error_detail",
        ] if c in alerts_df.columns]
        st.dataframe(alerts_df[display_cols], hide_index=True, width="stretch")
    else:
        st.caption("No alerts recorded yet.")

    st.markdown("#### Configuration")
    st.json({
        "project": config.project.model_dump(),
        "alerts": config.alerts.model_dump(),
        "observability": config.observability.model_dump(),
        "auth": {"provider": config.auth.provider, "enabled": config.auth.enabled},
        "budget": config.budget.model_dump(),
        "retention": config.retention.model_dump(),
    })
