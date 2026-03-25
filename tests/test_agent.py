"""Tests for agent.py — governed agent layer."""

import pytest
from schema import CompetitorEvent
from agent import (
    AgentGovernor, AgentTask,
    summarize_events, build_timeline, generate_competitor_brief, search_events,
)


def _make_event(event_id="e1", competitor="Siemens", confidence=0.8, **kw) -> CompetitorEvent:
    defaults = dict(
        event_id=event_id, competitor=competitor, event_type="API_UPDATE",
        title="Test SDK", description="SDK released",
        strategic_implication="ABB impact",
        confidence_score=confidence, source_url="https://example.com",
        date_detected="2026-03-19T00:00:00",
        signal_type="developer_api",
    )
    defaults.update(kw)
    return CompetitorEvent(**defaults)


class TestGovernor:
    def test_allowed_tool(self):
        gov = AgentGovernor()
        task = AgentTask(task_id="t1", task_type="summarize", description="test")
        assert gov.check_tool("summarize_events", task) is True

    def test_blocked_tool(self):
        gov = AgentGovernor()
        task = AgentTask(task_id="t1", task_type="test", description="test")
        assert gov.check_tool("browse_arbitrary_url", task) is False

    def test_unknown_tool(self):
        gov = AgentGovernor()
        task = AgentTask(task_id="t1", task_type="test", description="test")
        assert gov.check_tool("nonexistent_tool", task) is False

    def test_step_limit(self):
        gov = AgentGovernor(max_steps=2)
        task = AgentTask(task_id="t1", task_type="test", description="test", max_steps=2)
        task.steps_taken = 2
        assert gov.check_tool("summarize_events", task) is False

    def test_execute_tool(self):
        gov = AgentGovernor()
        task = AgentTask(task_id="t1", task_type="test", description="test")
        events = [_make_event()]
        result = gov.execute_tool(
            task, "summarize_events", summarize_events,
            input_summary="test", events=events,
        )
        assert result is not None
        assert result["total_events"] == 1
        assert task.steps_taken == 1

    def test_audit_log(self):
        gov = AgentGovernor()
        task = AgentTask(task_id="t1", task_type="test", description="test")
        gov.check_tool("browse_arbitrary_url", task)
        log = gov.get_full_audit_log()
        assert len(log) == 1
        assert log[0].status == "blocked"

    def test_require_approval(self):
        gov = AgentGovernor()
        task = AgentTask(task_id="t1", task_type="test", description="test")
        gov.require_approval(task, "high impact export")
        assert task.requires_approval is True
        assert task.status == "awaiting_approval"

    def test_approve_task(self):
        gov = AgentGovernor()
        task = AgentTask(task_id="t1", task_type="test", description="test")
        gov.require_approval(task, "needs review")
        gov.approve_task(task, "analyst_1")
        assert task.approved_by == "analyst_1"
        assert task.status == "running"


class TestBuiltInTools:
    def test_summarize_events(self):
        events = [
            _make_event(event_id="e1", competitor="Siemens", confidence=0.9),
            _make_event(event_id="e2", competitor="Schneider", confidence=0.4),
        ]
        result = summarize_events(events)
        assert result["total_events"] == 2
        assert "Siemens" in result["by_competitor"]
        assert len(result["high_confidence_events"]) == 1

    def test_build_timeline(self):
        events = [
            _make_event(event_id="e1", date_detected="2026-03-19T00:00:00"),
            _make_event(event_id="e2", date_detected="2026-03-20T00:00:00"),
        ]
        timeline = build_timeline(events)
        assert len(timeline) == 2
        assert timeline[0]["date"] == "2026-03-19"

    def test_generate_brief(self):
        events = [
            _make_event(event_id="e1", competitor="Siemens"),
            _make_event(event_id="e2", competitor="ABB"),
        ]
        brief = generate_competitor_brief(events, "Siemens")
        assert brief["competitor"] == "Siemens"
        assert brief["total_signals"] == 1

    def test_generate_brief_no_events(self):
        brief = generate_competitor_brief([], "Siemens")
        assert brief["status"] == "no_events"

    def test_search_events(self):
        events = [
            _make_event(event_id="e1", title="Edge AI SDK"),
            _make_event(event_id="e2", title="Cloud Platform Update"),
        ]
        results = search_events(events, "edge")
        assert len(results) == 1
        assert results[0]["event_id"] == "e1"

    def test_search_no_match(self):
        events = [_make_event(title="SDK release")]
        results = search_events(events, "quantum")
        assert len(results) == 0
