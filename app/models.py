"""Data models for job application tracking."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class JobApplication(BaseModel):
    """Represents a parsed job application from an email."""

    company: str
    position: str
    date_applied: date
    source_email_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: Optional[str] = None  # ATS domain or email sender
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    def to_row(self) -> list[str]:
        """Convert to spreadsheet row format: Position, Company, Date Applied."""
        return [
            self.position,
            self.company,
            self.date_applied.isoformat(),
        ]
