"""Schemas used by the normalizer worker."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

RejectedRaw = dict[str, object] | str


class RejectedStationMessage(BaseModel):
    """Envelope for records filtered during normalization."""

    message_id: str = Field(..., description="Original ingestion message identifier")
    source: Literal["catalunya", "valencia", "galicia"] = Field(
        ..., description="Original source identifier"
    )
    format: Literal["json", "xml", "csv"] = Field(..., description="Original payload format")
    reason: str = Field(..., description="Machine-readable rejection reason")
    rejection_level: Literal["message", "station"] = Field(
        ..., description="Whether rejection applies to whole message or one station"
    )
    raw_payload: RejectedRaw = Field(
        ..., description="Raw payload or station fragment rejected by normalizer"
    )
    rejected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when rejection was recorded",
    )
