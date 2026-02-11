"""Pydantic models for ITV stations domain."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ITVStation(BaseModel):
    """Normalized ITV Station model."""
    
    station_id: str = Field(..., description="Unique identifier for the station")
    name: str = Field(..., description="Station name")
    address: Optional[str] = Field(None, description="Physical address")
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    source_system: str = Field(..., description="Source system identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
