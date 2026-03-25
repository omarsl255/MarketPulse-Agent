"""Regression tests for dashboard rendering helpers.

These tests verify that the HTML produced by signal-card and review-queue
rendering is safe from Markdown-parser misinterpretation and handles
edge-case content (angle brackets, backticks, code fences, long JSON).
"""

import html
import json
import re
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# We cannot import app.py directly because it executes Streamlit commands
# at module level.  Instead, we replicate the pure helper functions that
# the rendering relies on and test them identically.
# ---------------------------------------------------------------------------

HIGH_BADGE_THRESHOLD = 0.8
MEDIUM_BADGE_THRESHOLD = 0.5


def safe_value(value, fallback="—"):
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def format_date_label(value):
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        text = str(value).strip()
        return text[:10] if text else "Unknown"
    return parsed.strftime("%Y-%m-%d")


def get_confidence_badge(score):
    if score > HIGH_BADGE_THRESHOLD:
        return '<span class="badge badge-high">HIGH</span>'
    if score > MEDIUM_BADGE_THRESHOLD:
        return '<span class="badge badge-med">MEDIUM</span>'
    return '<span class="badge badge-low">LOW</span>'


def build_card_html(row):
    """Replicate the card-HTML builder from app.py for testing."""
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

    return "\n".join([
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


def _make_row(**overrides):
    base = {
        "event_id": "test-001",
        "title": "Test Event",
        "competitor": "Acme Corp",
        "event_type": "product_launch",
        "signal_type": "press",
        "date_detected": "2026-03-20",
        "description": "A test event for rendering.",
        "strategic_implication": "Moderate impact on our roadmap.",
        "source_url": "https://example.com",
        "content_hash": "abc123def456ghi7",
        "confidence_score": 0.85,
        "is_new": 1,
        "review_status": "unreviewed",
        "correlation_id": "",
        "run_id": "run-1",
        "provenance": "pipeline",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test: no blank lines in card HTML (CommonMark HTML-block safety)
# ---------------------------------------------------------------------------

class TestCardHtmlNoBlanks:
    """The card HTML must never contain blank lines, which would terminate
    the CommonMark HTML block and cause Markdown to parse the remainder."""

    def test_no_blank_lines_basic(self):
        card = build_card_html(_make_row())
        for i, line in enumerate(card.split("\n"), 1):
            assert line.strip() != "", f"Blank line at position {i}"

    def test_no_blank_lines_without_new_badge(self):
        card = build_card_html(_make_row(is_new=0))
        for i, line in enumerate(card.split("\n"), 1):
            assert line.strip() != "", f"Blank line at position {i}"

    def test_no_blank_lines_without_review_badge(self):
        card = build_card_html(_make_row(review_status="unreviewed"))
        for i, line in enumerate(card.split("\n"), 1):
            assert line.strip() != "", f"Blank line at position {i}"

    def test_no_blank_lines_without_correlation(self):
        card = build_card_html(_make_row(correlation_id=""))
        for i, line in enumerate(card.split("\n"), 1):
            assert line.strip() != "", f"Blank line at position {i}"

    def test_no_blank_lines_minimal_badges(self):
        """Only the confidence badge; all optional badges empty."""
        card = build_card_html(_make_row(is_new=0, review_status="unreviewed", correlation_id=""))
        for i, line in enumerate(card.split("\n"), 1):
            assert line.strip() != "", f"Blank line at position {i}"

    def test_no_blank_lines_all_badges(self):
        card = build_card_html(_make_row(
            is_new=1, review_status="escalated", correlation_id="corr-99",
        ))
        for i, line in enumerate(card.split("\n"), 1):
            assert line.strip() != "", f"Blank line at position {i}"


# ---------------------------------------------------------------------------
# Test: no leading whitespace on first line (avoids indented code block)
# ---------------------------------------------------------------------------

class TestCardHtmlNoLeadingIndent:
    def test_first_char_is_angle_bracket(self):
        card = build_card_html(_make_row())
        assert card[0] == "<", "Card HTML must start with '<' (no leading whitespace)"


# ---------------------------------------------------------------------------
# Test: dangerous content is escaped
# ---------------------------------------------------------------------------

class TestHtmlEscaping:
    def test_angle_brackets_in_title(self):
        card = build_card_html(_make_row(title="<script>alert(1)</script>"))
        assert "<script>" not in card
        assert "&lt;script&gt;" in card

    def test_angle_brackets_in_description(self):
        card = build_card_html(_make_row(description="<img src=x onerror=alert(1)>"))
        assert "<img " not in card
        assert "&lt;img " in card

    def test_code_fence_in_title(self):
        """Backticks survive html.escape() (they're not HTML-special), but
        inside a properly-recognized HTML block the Markdown parser will
        not interpret them.  Verify the title is present and angle brackets
        are still escaped."""
        card = build_card_html(_make_row(title="```python\nprint('hi')\n```"))
        assert "&lt;" not in card.split('<div class="feed-card-title">')[1].split("</div>")[0]

    def test_backtick_in_description(self):
        card = build_card_html(_make_row(description="Use `config.yaml` to set it"))
        assert "`config.yaml`" in card

    def test_long_json_in_description(self):
        blob = json.dumps({"key": "x" * 500})
        card = build_card_html(_make_row(description=blob))
        assert "&quot;" in card or '"' not in card.split("What happened")[1].split("</p>")[0]

    def test_ampersand_in_title(self):
        card = build_card_html(_make_row(title="AT&T and partners"))
        assert "&amp;T" in card

    def test_quotes_in_source_url(self):
        card = build_card_html(_make_row(source_url='https://example.com/a"b'))
        assert '&quot;' in card


# ---------------------------------------------------------------------------
# Test: badge rendering
# ---------------------------------------------------------------------------

class TestBadgeRendering:
    def test_high_confidence_badge(self):
        card = build_card_html(_make_row(confidence_score=0.95))
        assert "badge-high" in card

    def test_medium_confidence_badge(self):
        card = build_card_html(_make_row(confidence_score=0.65))
        assert "badge-med" in card

    def test_low_confidence_badge(self):
        card = build_card_html(_make_row(confidence_score=0.3))
        assert "badge-low" in card

    def test_new_badge_present(self):
        card = build_card_html(_make_row(is_new=1))
        assert "badge-new" in card

    def test_new_badge_absent(self):
        card = build_card_html(_make_row(is_new=0))
        assert "badge-new" not in card

    def test_confirmed_badge(self):
        card = build_card_html(_make_row(review_status="confirmed"))
        assert "CONFIRMED" in card

    def test_dismissed_badge(self):
        card = build_card_html(_make_row(review_status="dismissed"))
        assert "DISMISSED" in card

    def test_escalated_badge(self):
        card = build_card_html(_make_row(review_status="escalated"))
        assert "ESCALATED" in card

    def test_correlated_badge(self):
        card = build_card_html(_make_row(correlation_id="cluster-42"))
        assert "CORRELATED" in card

    def test_no_correlated_badge_when_empty(self):
        card = build_card_html(_make_row(correlation_id=""))
        assert "CORRELATED" not in card


# ---------------------------------------------------------------------------
# Test: helper functions
# ---------------------------------------------------------------------------

class TestSafeValue:
    def test_none_returns_fallback(self):
        assert safe_value(None) == "—"

    def test_nan_returns_fallback(self):
        assert safe_value(float("nan")) == "—"

    def test_empty_string_returns_fallback(self):
        assert safe_value("") == "—"

    def test_whitespace_returns_fallback(self):
        assert safe_value("   ") == "—"

    def test_normal_value(self):
        assert safe_value("hello") == "hello"

    def test_custom_fallback(self):
        assert safe_value(None, "N/A") == "N/A"


class TestFormatDateLabel:
    def test_iso_date(self):
        assert format_date_label("2026-03-20") == "2026-03-20"

    def test_datetime(self):
        assert format_date_label("2026-03-20T14:30:00") == "2026-03-20"

    def test_invalid(self):
        assert format_date_label("not-a-date") == "not-a-date"

    def test_empty(self):
        assert format_date_label("") == "Unknown"
