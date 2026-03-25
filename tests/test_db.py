"""Tests for db.py — CRUD ops on in-memory SQLite."""

import pytest
import os
import tempfile
from schema import CompetitorEvent, FailedExtraction
from db import (
    init_db, save_event, get_all_events, get_events_by_run,
    get_events_by_competitor, save_snapshot, get_last_snapshot,
    clear_all_snapshots, count_snapshots,
    count_events_by_event_type, delete_events_by_event_type,
    save_failed_extraction, get_failed_extractions,
)


@pytest.fixture
def tmp_db():
    """Create a temporary database file for testing."""
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
        assert count_events_by_event_type("MOCK_SIGNAL", db_path=tmp_db) == 0
        assert len(get_all_events(db_path=tmp_db)) == 1

    def test_v2_columns(self, tmp_db):
        save_event(_make_event(), db_path=tmp_db)
        e = get_all_events(db_path=tmp_db)[0]
        assert e["run_id"] == "run1"
        assert e["signal_type"] == "developer_api"
        assert e["content_hash"] == "abc"
        assert e["is_new"] == 1


class TestSnapshots:
    def test_save_and_get(self, tmp_db):
        save_snapshot("https://example.com", "hash1", "raw text", "2026-01-01T00:00:00", db_path=tmp_db)
        snap = get_last_snapshot("https://example.com", db_path=tmp_db)
        assert snap is not None
        assert snap["content_hash"] == "hash1"

    def test_no_snapshot(self, tmp_db):
        snap = get_last_snapshot("https://nonexistent.com", db_path=tmp_db)
        assert snap is None

    def test_upsert_snapshot(self, tmp_db):
        save_snapshot("https://example.com", "hash1", "v1", "2026-01-01", db_path=tmp_db)
        save_snapshot("https://example.com", "hash2", "v2", "2026-01-02", db_path=tmp_db)
        snap = get_last_snapshot("https://example.com", db_path=tmp_db)
        assert snap["content_hash"] == "hash2"

    def test_count_and_clear_snapshots(self, tmp_db):
        assert count_snapshots(db_path=tmp_db) == 0
        save_snapshot("https://a.com", "h1", "t1", "2026-01-01", db_path=tmp_db)
        save_snapshot("https://b.com", "h2", "t2", "2026-01-02", db_path=tmp_db)
        assert count_snapshots(db_path=tmp_db) == 2
        n = clear_all_snapshots(db_path=tmp_db)
        assert n == 2
        assert count_snapshots(db_path=tmp_db) == 0
        assert get_last_snapshot("https://a.com", db_path=tmp_db) is None


class TestFailedExtractions:
    def test_save_and_get(self, tmp_db):
        f = FailedExtraction(
            id="f1", url="https://fail.com", error_message="Timeout",
            timestamp="2026-01-01T00:00:00", run_id="r1",
            failure_category="fetch_timeout",
            http_status_code=None,
            detail="timed out",
        )
        save_failed_extraction(f, db_path=tmp_db)
        fails = get_failed_extractions(db_path=tmp_db)
        assert len(fails) == 1
        assert fails[0]["error_message"] == "Timeout"
        assert fails[0]["failure_category"] == "fetch_timeout"
        assert fails[0]["detail"] == "timed out"
