"""Pydantic models for ITV stations domain."""

from datetime import datetime

from pydantic import BaseModel, Field


class ITVStation(BaseModel):
    """Normalized ITV Station model."""

    station_id: str = Field(..., description="Unique identifier for the station")
    name: str = Field(..., description="Station name")
    address: str | None = Field(None, description="Physical address")
    latitude: float | None = Field(None, description="Latitude coordinate")
    longitude: float | None = Field(None, description="Longitude coordinate")
    source_system: str = Field(..., description="Source system identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
