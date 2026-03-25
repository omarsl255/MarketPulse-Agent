"""Tests for notifier.py — alert routing."""

import pytest
from unittest.mock import patch
from schema import CompetitorEvent
from notifier import should_alert, send_alerts, _build_alert_message, _send_log


def _make_event(confidence=0.8, **kw) -> CompetitorEvent:
    defaults = dict(
        event_id="e1", competitor="Siemens", event_type="API_UPDATE",
        title="New SDK", description="Released v2",
        strategic_implication="Threatens ABB",
        confidence_score=confidence, source_url="https://example.com",
        date_detected="2026-03-19T00:00:00",
        run_id="r1", signal_type="developer_api",
    )
    defaults.update(kw)
    return CompetitorEvent(**defaults)


class TestShouldAlert:
    def test_high_confidence(self):
        assert should_alert(_make_event(confidence=0.9), min_confidence=0.7) is True

    def test_low_confidence(self):
        assert should_alert(_make_event(confidence=0.3), min_confidence=0.7) is False

    def test_threshold_boundary(self):
        assert should_alert(_make_event(confidence=0.7), min_confidence=0.7) is True


class TestBuildMessage:
    def test_contains_fields(self):
        msg = _build_alert_message(_make_event())
        assert "Siemens" in msg
        assert "New SDK" in msg
        assert "0.80" in msg


class TestSendLog:
    def test_returns_sent(self):
        alert = _send_log(_make_event())
        assert alert.status == "sent"
        assert alert.channel == "log"
        assert alert.event_id == "e1"


class TestSendAlerts:
    def test_log_channel(self):
        events = [_make_event(confidence=0.9)]
        records = send_alerts(events, channels=["log"], min_confidence=0.7)
        assert len(records) == 1
        assert records[0].status == "sent"

    def test_skips_low_confidence(self):
        events = [_make_event(confidence=0.3)]
        records = send_alerts(events, channels=["log"], min_confidence=0.7)
        assert len(records) == 0

    def test_max_alerts_cap(self):
        events = [_make_event(event_id=f"e{i}", confidence=0.9) for i in range(10)]
        records = send_alerts(events, channels=["log"], min_confidence=0.7, max_alerts=3)
        sent = [r for r in records if r.status == "sent"]
        assert len(sent) <= 3

    def test_slack_without_env(self):
        events = [_make_event(confidence=0.9)]
        with patch.dict("os.environ", {}, clear=True):
            records = send_alerts(events, channels=["slack"], min_confidence=0.7)
        assert len(records) == 1
        assert records[0].status == "failed"
        assert "SLACK_WEBHOOK_URL" in records[0].error_detail
