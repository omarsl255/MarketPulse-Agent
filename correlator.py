"""
correlator.py — V3 cross-signal correlation engine.
Detects when multiple events from different signals or competitors
align around a common strategic theme.
Phase 1: deterministic heuristic matching.
Phase 2 (future): LLM-based synthesis.
"""

import uuid
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from schema import CompetitorEvent, CorrelationCluster

logger = logging.getLogger("correlator")

# Heuristic keyword groups that suggest strategic themes
THEME_KEYWORDS: Dict[str, List[str]] = {
    "edge_computing": ["edge", "iot", "gateway", "industrial edge", "edge ai", "edge device"],
    "digital_twin": ["digital twin", "simulation", "virtual commissioning", "twin"],
    "open_source_push": ["open source", "github", "oss", "open-source", "community"],
    "api_platform": ["api", "sdk", "developer portal", "developer ecosystem", "openapi"],
    "ai_ml_strategy": ["ai", "machine learning", "ml", "deep learning", "neural", "generative"],
    "sustainability": ["sustainability", "carbon", "energy efficiency", "green", "circular"],
    "cloud_expansion": ["cloud", "saas", "aws", "azure", "gcp", "kubernetes"],
    "partnership_m_and_a": ["partnership", "acquisition", "joint venture", "collaboration", "merger"],
    "workforce_shift": ["hiring", "layoff", "restructuring", "talent", "careers"],
    "protocol_standards": ["opc ua", "mqtt", "profinet", "tsn", "modbus", "fieldbus"],
}


def _match_themes(text: str) -> List[str]:
    """Return theme labels that match keywords in the text."""
    lower = text.lower()
    matched = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            matched.append(theme)
    return matched


def find_correlations(
    events: List[CompetitorEvent],
    *,
    time_window_days: int = 14,
    min_cluster_size: int = 2,
    run_id: str = "",
) -> List[CorrelationCluster]:
    """
    Group events by shared themes within a time window.
    Returns CorrelationCluster objects for clusters that span
    multiple signals or competitors.
    """
    if len(events) < min_cluster_size:
        return []

    theme_buckets: Dict[str, List[CompetitorEvent]] = defaultdict(list)

    for event in events:
        searchable = f"{event.title} {event.description} {event.strategic_implication}"
        themes = _match_themes(searchable)
        for theme in themes:
            theme_buckets[theme].append(event)

    clusters: List[CorrelationCluster] = []
    now = datetime.now()

    for theme, bucket_events in theme_buckets.items():
        if len(bucket_events) < min_cluster_size:
            continue

        recent = [
            e for e in bucket_events
            if _is_recent(e.date_detected, time_window_days, now)
        ]
        if len(recent) < min_cluster_size:
            continue

        competitors = list(set(e.competitor for e in recent))
        signal_types = list(set(e.signal_type for e in recent))

        spans_multiple = len(competitors) > 1 or len(signal_types) > 1
        if not spans_multiple:
            continue

        strength = _compute_strength(recent, competitors, signal_types)

        cluster = CorrelationCluster(
            cluster_id=str(uuid.uuid4())[:12],
            label=theme.replace("_", " ").title(),
            description=(
                f"Detected {len(recent)} related events across "
                f"{len(competitors)} competitor(s) and {len(signal_types)} signal type(s) "
                f"in the last {time_window_days} days."
            ),
            event_ids=[e.event_id for e in recent],
            competitors=competitors,
            signal_types=signal_types,
            strength=strength,
            created_at=now.isoformat(),
            run_id=run_id,
        )
        clusters.append(cluster)
        logger.info(
            f"Correlation: '{theme}' — {len(recent)} events, "
            f"competitors={competitors}, signals={signal_types}, strength={strength:.2f}"
        )

    return clusters


def _is_recent(date_str: str, window_days: int, now: datetime) -> bool:
    try:
        dt = datetime.fromisoformat(date_str)
        return (now - dt) < timedelta(days=window_days)
    except (ValueError, TypeError):
        return False


def _compute_strength(
    events: List[CompetitorEvent],
    competitors: List[str],
    signal_types: List[str],
) -> float:
    """
    Heuristic strength score:
    - more events, more competitors, more signal types = stronger
    - higher average confidence = stronger
    """
    avg_conf = sum(e.confidence_score for e in events) / max(len(events), 1)
    breadth = (len(competitors) + len(signal_types)) / 10.0
    volume = min(len(events) / 10.0, 1.0)
    raw = (avg_conf * 0.5) + (breadth * 0.3) + (volume * 0.2)
    return round(min(raw, 1.0), 2)
