"""Tests for db.py — CRUD ops on in-memory SQLite (V3)."""

import pytest
import os
import tempfile
from schema import (
    CompetitorEvent, FailedExtraction, RunMetadata,
    AlertRecord, AnalystReview, CorrelationCluster, BudgetUsage,
)
from db import (
    init_db, save_event, get_all_events, get_events_by_run,
    get_events_by_competitor, save_snapshot, get_last_snapshot,
    clear_all_snapshots, count_snapshots,
    count_events_by_event_type, delete_events_by_event_type,
    save_failed_extraction, get_failed_extractions,
    save_run, get_all_runs,
    save_alert, get_all_alerts, get_alerts_by_run,
    save_review, get_reviews_for_event, get_unreviewed_events,
    update_event_review, update_event_alert_status, update_event_correlation,
    save_correlation, get_all_correlations,
    save_budget_usage, get_budget_for_run,
)


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


def _make_event(**overrides) -> CompetitorEvent:
    defaults = dict(
        event_id="e1", competitor="Siemens", event_type="API_UPDATE",
        title="Test", description="desc", strategic_implication="impact",
        confidence_score=0.7, source_url="https://example.com",
        date_detected="2026-03-19T00:00:00",
        run_id="run1", signal_type="developer_api", content_hash="abc", is_new=True,
    )
    defaults.update(overrides)
    return CompetitorEvent(**defaults)


class TestEvents:
    def test_save_and_get(self, tmp_db):
        save_event(_make_event(), db_path=tmp_db)
        events = get_all_events(db_path=tmp_db)
        assert len(events) == 1
        assert events[0]["title"] == "Test"

    def test_upsert(self, tmp_db):
        save_event(_make_event(title="v1"), db_path=tmp_db)
        save_event(_make_event(title="v2"), db_path=tmp_db)
        events = get_all_events(db_path=tmp_db)
        assert len(events) == 1
        assert events[0]["title"] == "v2"

    def test_get_by_run(self, tmp_db):
        save_event(_make_event(event_id="e1", run_id="r1"), db_path=tmp_db)
        save_event(_make_event(event_id="e2", run_id="r2"), db_path=tmp_db)
        assert len(get_events_by_run("r1", db_path=tmp_db)) == 1

    def test_get_by_competitor(self, tmp_db):
        save_event(_make_event(event_id="e1", competitor="Siemens"), db_path=tmp_db)
        save_event(_make_event(event_id="e2", competitor="ABB"), db_path=tmp_db)
        assert len(get_events_by_competitor("Siemens", db_path=tmp_db)) == 1

    def test_delete_by_event_type(self, tmp_db):
        save_event(_make_event(event_id="e1", event_type="MOCK_SIGNAL"), db_path=tmp_db)
        save_event(_make_event(event_id="e2", event_type="REAL"), db_path=tmp_db)
        assert count_events_by_event_type("MOCK_SIGNAL", db_path=tmp_db) == 1
        n = delete_events_by_event_type("MOCK_SIGNAL", db_path=tmp_db)
        assert n == 1
        assert len(get_all_events(db_path=tmp_db)) == 1

    def test_v3_columns(self, tmp_db):
        save_event(_make_event(), db_path=tmp_db)
        e = get_all_events(db_path=tmp_db)[0]
        assert e["review_status"] == "unreviewed"
        assert e["alert_status"] == "pending"
        assert e["provenance"] == "pipeline"

    def test_update_review(self, tmp_db):
        save_event(_make_event(), db_path=tmp_db)
        update_event_review("e1", "confirmed", db_path=tmp_db)
        e = get_all_events(db_path=tmp_db)[0]
        assert e["review_status"] == "confirmed"

    def test_update_alert_status(self, tmp_db):
        save_event(_make_event(), db_path=tmp_db)
        update_event_alert_status("e1", "sent", db_path=tmp_db)
        e = get_all_events(db_path=tmp_db)[0]
        assert e["alert_status"] == "sent"

    def test_update_correlation(self, tmp_db):
        save_event(_make_event(), db_path=tmp_db)
        update_event_correlation("e1", "cluster_abc", db_path=tmp_db)
        e = get_all_events(db_path=tmp_db)[0]
        assert e["correlation_id"] == "cluster_abc"

    def test_unreviewed_events(self, tmp_db):
        save_event(_make_event(event_id="e1"), db_path=tmp_db)
        save_event(_make_event(event_id="e2", review_status="confirmed"), db_path=tmp_db)
        unreviewed = get_unreviewed_events(db_path=tmp_db)
        assert len(unreviewed) == 1
        assert unreviewed[0]["event_id"] == "e1"


class TestSnapshots:
    def test_save_and_get(self, tmp_db):
        save_snapshot("https://example.com", "hash1", "raw text", "2026-01-01T00:00:00", db_path=tmp_db)
        snap = get_last_snapshot("https://example.com", db_path=tmp_db)
        assert snap is not None
        assert snap["content_hash"] == "hash1"

    def test_no_snapshot(self, tmp_db):
        assert get_last_snapshot("https://nonexistent.com", db_path=tmp_db) is None

    def test_count_and_clear(self, tmp_db):
        save_snapshot("https://a.com", "h1", "t1", "2026-01-01", db_path=tmp_db)
        save_snapshot("https://b.com", "h2", "t2", "2026-01-02", db_path=tmp_db)
        assert count_snapshots(db_path=tmp_db) == 2
        n = clear_all_snapshots(db_path=tmp_db)
        assert n == 2
        assert count_snapshots(db_path=tmp_db) == 0


class TestFailedExtractions:
    def test_save_and_get(self, tmp_db):
        f = FailedExtraction(
            id="f1", url="https://fail.com", error_message="Timeout",
            timestamp="2026-01-01T00:00:00", run_id="r1",
            failure_category="fetch_timeout", detail="timed out",
        )
        save_failed_extraction(f, db_path=tmp_db)
        fails = get_failed_extractions(db_path=tmp_db)
        assert len(fails) == 1
        assert fails[0]["failure_category"] == "fetch_timeout"


class TestRuns:
    def test_save_and_get(self, tmp_db):
        r = RunMetadata(
            run_id="r1", started_at="2026-01-01T00:00:00",
            status="completed", total_urls=10, events_extracted=5,
            trigger="manual",
        )
        save_run(r, db_path=tmp_db)
        runs = get_all_runs(db_path=tmp_db)
        assert len(runs) == 1
        assert runs[0]["run_id"] == "r1"
        assert runs[0]["trigger"] == "manual"

    def test_upsert_run(self, tmp_db):
        save_run(RunMetadata(run_id="r1", started_at="2026-01-01", status="running"), db_path=tmp_db)
        save_run(RunMetadata(run_id="r1", started_at="2026-01-01", status="completed"), db_path=tmp_db)
        runs = get_all_runs(db_path=tmp_db)
        assert len(runs) == 1
        assert runs[0]["status"] == "completed"


class TestAlerts:
    def test_save_and_get(self, tmp_db):
        a = AlertRecord(
            alert_id="a1", event_id="e1", channel="log",
            status="sent", created_at="2026-01-01T00:00:00",
            run_id="r1",
        )
        save_alert(a, db_path=tmp_db)
        alerts = get_all_alerts(db_path=tmp_db)
        assert len(alerts) == 1
        assert alerts[0]["channel"] == "log"

    def test_get_by_run(self, tmp_db):
        save_alert(AlertRecord(
            alert_id="a1", event_id="e1", channel="log",
            created_at="2026-01-01", run_id="r1",
        ), db_path=tmp_db)
        save_alert(AlertRecord(
            alert_id="a2", event_id="e2", channel="slack",
            created_at="2026-01-01", run_id="r2",
        ), db_path=tmp_db)
        assert len(get_alerts_by_run("r1", db_path=tmp_db)) == 1


class TestReviews:
    def test_save_and_get(self, tmp_db):
        r = AnalystReview(
            review_id="rv1", event_id="e1", verdict="confirmed",
            reviewed_at="2026-01-01T00:00:00",
        )
        save_review(r, db_path=tmp_db)
        reviews = get_reviews_for_event("e1", db_path=tmp_db)
        assert len(reviews) == 1
        assert reviews[0]["verdict"] == "confirmed"


class TestCorrelations:
    def test_save_and_get(self, tmp_db):
        c = CorrelationCluster(
            cluster_id="c1", label="Edge AI",
            event_ids=["e1", "e2"], competitors=["Siemens"],
            signal_types=["developer_api"], strength=0.8,
            created_at="2026-01-01T00:00:00",
        )
        save_correlation(c, db_path=tmp_db)
        clusters = get_all_correlations(db_path=tmp_db)
        assert len(clusters) == 1
        assert clusters[0]["label"] == "Edge AI"
        assert clusters[0]["event_ids"] == ["e1", "e2"]


class TestBudget:
    def test_save_and_sum(self, tmp_db):
        save_budget_usage(BudgetUsage(
            run_id="r1", stage="extraction", tokens_used=1000, llm_calls=5,
            timestamp="2026-01-01",
        ), db_path=tmp_db)
        save_budget_usage(BudgetUsage(
            run_id="r1", stage="calibration", tokens_used=500, llm_calls=3,
            timestamp="2026-01-01",
        ), db_path=tmp_db)
        totals = get_budget_for_run("r1", db_path=tmp_db)
        assert totals["tokens"] == 1500
        assert totals["calls"] == 8
