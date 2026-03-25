"""
schema.py — Pydantic data models for V2.
Backward-compatible with V1 CompetitorEvent fields.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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
    # --- V2 additions ---
    run_id: str = Field(default="", description="Pipeline run identifier")
    signal_type: str = Field(default="unknown", description="Signal category (developer_api, github, patent, etc.)")
    content_hash: str = Field(default="", description="SHA-256 hash of the source content")
    is_new: bool = Field(default=True, description="True if this content changed since last run")


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
