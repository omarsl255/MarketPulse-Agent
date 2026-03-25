"""Tests for schema.py — Pydantic model validation."""

import pytest
from schema import CompetitorEvent, ContentSnapshot, FailedExtraction, SignalSource, CompetitorProfile, StrategicTheme


class TestCompetitorEvent:
    def test_v1_fields(self):
        """V1 fields still work."""
        event = CompetitorEvent(
            event_id="e1",
            competitor="Siemens",
            event_type="API_UPDATE",
            title="New SDK",
            description="Released v2 SDK",
            strategic_implication="Threatens ABB developer lock-in",
            confidence_score=0.85,
            source_url="https://developer.siemens.com",
            date_detected="2026-03-19T00:00:00",
        )
        assert event.event_id == "e1"
        assert event.confidence_score == 0.85

    def test_v2_defaults(self):
        """V2 fields have sensible defaults."""
        event = CompetitorEvent(
            event_id="e2",
            competitor="Siemens",
            event_type="TEST",
            title="T",
            description="D",
            strategic_implication="S",
            confidence_score=0.5,
            source_url="https://example.com",
            date_detected="2026-01-01",
        )
        assert event.run_id == ""
        assert event.signal_type == "unknown"
        assert event.content_hash == ""
        assert event.is_new is True

    def test_confidence_boundaries(self):
        """Confidence score accepts edge values."""
        for score in [0.0, 0.5, 1.0]:
            e = CompetitorEvent(
                event_id="x", competitor="X", event_type="X", title="X",
                description="X", strategic_implication="X",
                confidence_score=score, source_url="http://x", date_detected="2026-01-01",
            )
            assert e.confidence_score == score


class TestContentSnapshot:
    def test_create(self):
        snap = ContentSnapshot(
            url="https://example.com",
            content_hash="abc123",
            last_updated="2026-01-01T00:00:00",
        )
        assert snap.raw_text == ""


class TestFailedExtraction:
    def test_create(self):
        f = FailedExtraction(
            id="f1",
            url="https://fail.com",
            error_message="Timeout",
            timestamp="2026-01-01T00:00:00",
        )
        assert f.raw_text_snippet == ""
        assert f.run_id == ""
        assert f.failure_category == ""
        assert f.http_status_code is None
        assert f.detail == ""


class TestSignalSource:
    def test_defaults(self):
        s = SignalSource(url="https://x.com", competitor="X", signal_type="github")
        assert s.status == "active"
        assert s.last_checked is None


class TestCompetitorProfile:
    def test_defaults(self):
        p = CompetitorProfile(name="Siemens")
        assert p.industry == "Industrial Automation"
        assert p.known_products == []


class TestStrategicTheme:
    def test_create(self):
        t = StrategicTheme(theme_id="t1", name="Edge Push")
        assert t.related_event_ids == []
        assert t.confidence == 0.0
