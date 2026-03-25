"""Tests for schema.py — Pydantic model validation (V3)."""

import pytest
from schema import (
    CompetitorEvent, ContentSnapshot, FailedExtraction, SignalSource,
    CompetitorProfile, StrategicTheme,
    RunMetadata, AlertRecord, AnalystReview, CorrelationCluster, BudgetUsage,
)


class TestCompetitorEvent:
    def test_v1_fields(self):
        event = CompetitorEvent(
            event_id="e1", competitor="Siemens", event_type="API_UPDATE",
            title="New SDK", description="Released v2 SDK",
            strategic_implication="Threatens ABB developer lock-in",
            confidence_score=0.85, source_url="https://developer.siemens.com",
            date_detected="2026-03-19T00:00:00",
        )
        assert event.event_id == "e1"
        assert event.confidence_score == 0.85

    def test_v2_defaults(self):
        event = CompetitorEvent(
            event_id="e2", competitor="Siemens", event_type="TEST",
            title="T", description="D", strategic_implication="S",
            confidence_score=0.5, source_url="https://example.com",
            date_detected="2026-01-01",
        )
        assert event.run_id == ""
        assert event.signal_type == "unknown"
        assert event.content_hash == ""
        assert event.is_new is True

    def test_v3_defaults(self):
        event = CompetitorEvent(
            event_id="e3", competitor="Siemens", event_type="TEST",
            title="T", description="D", strategic_implication="S",
            confidence_score=0.5, source_url="https://example.com",
            date_detected="2026-01-01",
        )
        assert event.review_status == "unreviewed"
        assert event.alert_status == "pending"
        assert event.correlation_id == ""
        assert event.provenance == "pipeline"
        assert event.extraction_model == ""
        assert event.extraction_tokens == 0
        assert event.calibration_tokens == 0

    def test_confidence_boundaries(self):
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
            url="https://example.com", content_hash="abc123",
            last_updated="2026-01-01T00:00:00",
        )
        assert snap.raw_text == ""


class TestFailedExtraction:
    def test_create(self):
        f = FailedExtraction(
            id="f1", url="https://fail.com", error_message="Timeout",
            timestamp="2026-01-01T00:00:00",
        )
        assert f.raw_text_snippet == ""
        assert f.run_id == ""
        assert f.failure_category == ""
        assert f.http_status_code is None


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


class TestRunMetadata:
    def test_defaults(self):
        r = RunMetadata(run_id="r1", started_at="2026-01-01T00:00:00")
        assert r.status == "running"
        assert r.total_tokens == 0
        assert r.trigger == "manual"

    def test_full(self):
        r = RunMetadata(
            run_id="r2", started_at="2026-01-01", finished_at="2026-01-01T01:00:00",
            status="completed", total_urls=10, urls_changed=3,
            events_extracted=5, alerts_sent=2, trigger="scheduler",
        )
        assert r.events_extracted == 5
        assert r.trigger == "scheduler"


class TestAlertRecord:
    def test_create(self):
        a = AlertRecord(
            alert_id="a1", event_id="e1", channel="slack",
            created_at="2026-01-01T00:00:00",
        )
        assert a.status == "pending"
        assert a.sent_at == ""

    def test_sent(self):
        a = AlertRecord(
            alert_id="a2", event_id="e2", channel="log",
            status="sent", created_at="2026-01-01", sent_at="2026-01-01T00:01:00",
        )
        assert a.status == "sent"


class TestAnalystReview:
    def test_create(self):
        r = AnalystReview(review_id="rv1", event_id="e1")
        assert r.verdict == "unreviewed"
        assert r.reviewer == ""


class TestCorrelationCluster:
    def test_create(self):
        c = CorrelationCluster(
            cluster_id="c1", label="Edge AI Push",
            event_ids=["e1", "e2"], competitors=["Siemens", "Schneider"],
            signal_types=["developer_api", "github"], strength=0.75,
        )
        assert len(c.event_ids) == 2
        assert c.strength == 0.75


class TestBudgetUsage:
    def test_create(self):
        b = BudgetUsage(run_id="r1", stage="extraction", tokens_used=1000, llm_calls=5)
        assert b.tokens_used == 1000
