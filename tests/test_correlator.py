"""Tests for correlator.py — cross-signal correlation."""

import pytest
from datetime import datetime
from schema import CompetitorEvent
from correlator import find_correlations, _match_themes


def _make_event(
    event_id="e1", competitor="Siemens", signal_type="developer_api",
    title="Edge AI SDK released", description="New edge computing SDK",
    implication="ABB edge strategy", confidence=0.8,
    date_detected=None, **kw,
) -> CompetitorEvent:
    return CompetitorEvent(
        event_id=event_id, competitor=competitor, event_type="API_UPDATE",
        title=title, description=description,
        strategic_implication=implication,
        confidence_score=confidence, source_url="https://example.com",
        date_detected=date_detected or datetime.now().isoformat(),
        signal_type=signal_type, **kw,
    )


class TestMatchThemes:
    def test_matches_edge(self):
        themes = _match_themes("New edge computing SDK for IoT devices")
        assert "edge_computing" in themes

    def test_matches_ai(self):
        themes = _match_themes("Machine learning model deployment")
        assert "ai_ml_strategy" in themes

    def test_no_match(self):
        themes = _match_themes("Company annual report summary")
        assert len(themes) == 0


class TestFindCorrelations:
    def test_no_events(self):
        assert find_correlations([]) == []

    def test_single_event(self):
        assert find_correlations([_make_event()]) == []

    def test_same_competitor_same_signal_no_cluster(self):
        """Events from same competitor + signal type should not form a cluster."""
        events = [
            _make_event(event_id="e1", competitor="Siemens", signal_type="developer_api",
                        title="Edge SDK v1"),
            _make_event(event_id="e2", competitor="Siemens", signal_type="developer_api",
                        title="Edge SDK v2"),
        ]
        clusters = find_correlations(events, min_cluster_size=2)
        assert len(clusters) == 0

    def test_cross_competitor_cluster(self):
        """Events from different competitors sharing a theme should cluster."""
        events = [
            _make_event(event_id="e1", competitor="Siemens", signal_type="developer_api",
                        title="Edge AI platform launched"),
            _make_event(event_id="e2", competitor="Schneider", signal_type="github",
                        title="Edge computing SDK open-sourced"),
        ]
        clusters = find_correlations(events, min_cluster_size=2)
        assert len(clusters) >= 1
        cluster = clusters[0]
        assert len(cluster.event_ids) >= 2
        assert cluster.strength > 0

    def test_cross_signal_cluster(self):
        """Events from same competitor but different signals should cluster."""
        events = [
            _make_event(event_id="e1", competitor="Siemens", signal_type="developer_api",
                        title="New API for edge devices"),
            _make_event(event_id="e2", competitor="Siemens", signal_type="github",
                        title="Edge IoT gateway repository created"),
        ]
        clusters = find_correlations(events, min_cluster_size=2)
        assert len(clusters) >= 1
