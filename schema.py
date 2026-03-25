"""
schema.py — Pydantic data models for V3.
Backward-compatible with V1/V2 CompetitorEvent fields.
Adds: AlertRecord, RunMetadata, AnalystReview, CorrelationCluster, BudgetLimits.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AlertStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"
    ACKNOWLEDGED = "acknowledged"


class ReviewVerdict(str, Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    ESCALATED = "escalated"


class CompetitorEvent(BaseModel):
    """A single strategic signal detected from a competitor."""
    event_id: str = Field(description="Unique identifier for the event")
    competitor: str = Field(description="Name of the competitor (e.g., Siemens)")
    event_type: str = Field(description="Category of the event (e.g., API_UPDATE, NEW_SUBDOMAIN)")
    title: str = Field(description="Short title of the event")
    description: str = Field(description="Detailed description of what changed")
    strategic_implication: str = Field(description="Why this matters to the employer (e.g., ABB)")
    confidence_score: float = Field(description="Confidence in the signal from 0.0 to 1.0")
    source_url: str = Field(description="URL where the signal was detected")
    date_detected: str = Field(description="Date the event was detected in ISO format")
    # V2 additions
    run_id: str = Field(default="", description="Pipeline run identifier")
    signal_type: str = Field(default="unknown", description="Signal category (developer_api, github, patent, etc.)")
    content_hash: str = Field(default="", description="SHA-256 hash of the source content")
    is_new: bool = Field(default=True, description="True if this content changed since last run")
    # V3 additions
    review_status: str = Field(default="unreviewed", description="Analyst review status")
    alert_status: str = Field(default="pending", description="Alert delivery status")
    correlation_id: str = Field(default="", description="ID of the correlation cluster this event belongs to")
    provenance: str = Field(default="pipeline", description="How this event was created: pipeline, agent, manual")
    extraction_model: str = Field(default="", description="LLM model used for extraction")
    extraction_tokens: int = Field(default=0, description="Approximate token count used for extraction")
    calibration_tokens: int = Field(default=0, description="Approximate token count used for calibration")


class ContentSnapshot(BaseModel):
    """Stores a snapshot of raw page content for change detection."""
    url: str = Field(description="URL of the page")
    content_hash: str = Field(description="SHA-256 hash of the page text")
    raw_text: str = Field(default="", description="Raw text content (may be truncated)")
    last_updated: str = Field(description="ISO timestamp of when this snapshot was taken")


class SignalSource(BaseModel):
    """A monitored URL with metadata about its signal type and status."""
    url: str = Field(description="URL being monitored")
    competitor: str = Field(description="Competitor this source belongs to")
    signal_type: str = Field(description="Type of signal (developer_api, github, patent, etc.)")
    last_checked: Optional[str] = Field(default=None, description="ISO timestamp of last check")
    status: str = Field(default="active", description="Source status (active, error, disabled)")


class CompetitorProfile(BaseModel):
    """Metadata about a competitor being monitored."""
    name: str = Field(description="Competitor name")
    industry: str = Field(default="Industrial Automation", description="Primary industry")
    known_products: List[str] = Field(default_factory=list, description="Key product lines")
    strategic_stance: str = Field(default="", description="Overall strategic posture summary")


class StrategicTheme(BaseModel):
    """Groups related events under a strategic theme for pattern recognition."""
    theme_id: str = Field(description="Unique theme identifier")
    name: str = Field(description="Theme name (e.g., 'Edge Computing Push')")
    description: str = Field(default="", description="What this theme represents")
    related_event_ids: List[str] = Field(default_factory=list, description="Event IDs linked to this theme")
    confidence: float = Field(default=0.0, description="Overall confidence in this theme")


class FailedExtraction(BaseModel):
    """Record of a failed LLM extraction for the dead-letter queue."""
    id: str = Field(description="Unique identifier")
    url: str = Field(description="URL that failed extraction")
    error_message: str = Field(description="Error details")
    raw_text_snippet: str = Field(default="", description="First N chars of raw text for debugging")
    timestamp: str = Field(description="ISO timestamp of the failure")
    run_id: str = Field(default="", description="Pipeline run identifier")
    failure_category: str = Field(
        default="",
        description="Machine-readable class: fetch_timeout, fetch_http_error, llm_no_events, etc.",
    )
    http_status_code: Optional[int] = Field(
        default=None,
        description="HTTP status when fetch failed after a response (if applicable)",
    )
    detail: str = Field(default="", description="Extra technical detail for debugging")


# ─── V3 Models ────────────────────────────────────────────────


class RunMetadata(BaseModel):
    """Tracks a single pipeline execution with aggregated stats."""
    run_id: str = Field(description="Unique run identifier")
    started_at: str = Field(description="ISO timestamp when the run started")
    finished_at: str = Field(default="", description="ISO timestamp when the run finished")
    status: str = Field(default="running", description="running, completed, failed")
    total_urls: int = Field(default=0)
    urls_changed: int = Field(default=0)
    urls_unchanged: int = Field(default=0)
    urls_failed: int = Field(default=0)
    events_extracted: int = Field(default=0)
    extractions_failed: int = Field(default=0)
    alerts_sent: int = Field(default=0)
    total_tokens: int = Field(default=0, description="Total LLM tokens consumed in this run")
    correlations_found: int = Field(default=0)
    trigger: str = Field(default="manual", description="manual, scheduler, api")


class AlertRecord(BaseModel):
    """Tracks an individual alert delivery attempt."""
    alert_id: str = Field(description="Unique alert identifier")
    event_id: str = Field(description="The event that triggered this alert")
    channel: str = Field(description="Delivery channel: slack, teams, email, log")
    status: str = Field(default="pending", description="pending, sent, failed, suppressed")
    created_at: str = Field(description="ISO timestamp when the alert was created")
    sent_at: str = Field(default="", description="ISO timestamp when delivery succeeded")
    error_detail: str = Field(default="", description="Error info if delivery failed")
    run_id: str = Field(default="", description="Pipeline run that created this alert")


class AnalystReview(BaseModel):
    """Records an analyst's assessment of an event."""
    review_id: str = Field(description="Unique review identifier")
    event_id: str = Field(description="The event being reviewed")
    verdict: str = Field(default="unreviewed", description="unreviewed, confirmed, dismissed, escalated")
    reviewer: str = Field(default="", description="Analyst identifier")
    notes: str = Field(default="", description="Free-text analyst notes")
    reviewed_at: str = Field(default="", description="ISO timestamp of the review")


class CorrelationCluster(BaseModel):
    """Groups events that share a strategic signal pattern."""
    cluster_id: str = Field(description="Unique cluster identifier")
    label: str = Field(description="Short name for the correlation (e.g., 'Edge AI Push')")
    description: str = Field(default="", description="What ties these events together")
    event_ids: List[str] = Field(default_factory=list, description="Event IDs in this cluster")
    competitors: List[str] = Field(default_factory=list, description="Competitors involved")
    signal_types: List[str] = Field(default_factory=list, description="Signal types spanned")
    strength: float = Field(default=0.0, description="Correlation strength 0.0-1.0")
    created_at: str = Field(default="", description="ISO timestamp")
    run_id: str = Field(default="", description="Run that created this cluster")


class BudgetUsage(BaseModel):
    """Token and cost tracking for a pipeline run."""
    run_id: str = Field(description="Pipeline run identifier")
    competitor: str = Field(default="", description="Competitor scope (empty = global)")
    stage: str = Field(default="", description="extraction, calibration, correlation, agent")
    tokens_used: int = Field(default=0)
    llm_calls: int = Field(default=0)
    timestamp: str = Field(default="")
