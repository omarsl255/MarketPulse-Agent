from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CompetitorEvent(BaseModel):
    event_id: str = Field(description="Unique identifier for the event")
    competitor: str = Field(description="Name of the competitor (e.g., Siemens)")
    event_type: str = Field(description="Category of the event (e.g., API_UPDATE, NEW_SUBDOMAIN)")
    title: str = Field(description="Short title of the event")
    description: str = Field(description="Detailed description of what changed")
    strategic_implication: str = Field(description="Why this matters to the employer (e.g., ABB/Schneider)")
    confidence_score: float = Field(description="Confidence in the signal from 0.0 to 1.0")
    source_url: str = Field(description="URL where the signal was detected")
    date_detected: str = Field(description="Date the event was detected in ISO format")
