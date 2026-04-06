"""
Normalized Station Schema - Universal output model.

This model represents the standardized format for ITV station data after
normalization, regardless of the source system.
"""

from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class NormalizedStation(BaseModel):
    """
    Universal normalized model for ITV station data.

    This is the OUTPUT contract that all transformers must produce,
    ensuring consistency across different data sources (Catalunya, Valencia, Galicia).

    Attributes:
        station_id: Unique identifier with source prefix (e.g., CAT_001, VAL_042).
        name: Station name (cleaned and normalized).
        address: Full physical address.
        city: City name (normalized to UPPERCASE for consistency).
        province: Province name (normalized to UPPERCASE for consistency).
        postal_code: Spanish postal code (5 digits).
        latitude: Latitude coordinate (validated within Spain bounds).
        longitude: Longitude coordinate (validated within Spain bounds).
        phone: Contact phone number (cleaned format).
        email: Contact email address.
        source_system: Original data source (catalunya, valencia, galicia).
        raw_id: Original ID from source system (for traceability).
        normalized_at: Timestamp when normalization occurred (UTC).
    """

    # Required fields
    station_id: str = Field(
        ...,
        description="Unique identifier with source prefix (e.g., CAT_001)",
        min_length=3,
        max_length=50,
    )
    name: str = Field(
        ...,
        description="Station name",
        min_length=1,
        max_length=200,
    )
    source_system: Literal["catalunya", "valencia", "galicia"] = Field(
        ...,
        description="Source system identifier",
    )

    # Location fields
    address: Optional[str] = Field(
        None,
        description="Full physical address",
        max_length=500,
    )
    city: Optional[str] = Field(
        None,
        description="City name (normalized to UPPERCASE)",
        max_length=100,
    )
    province: Optional[str] = Field(
        None,
        description="Province name (normalized to UPPERCASE)",
        max_length=100,
    )
    postal_code: Optional[str] = Field(
        None,
        description="Spanish postal code (5 digits)",
        pattern=r"^\d{5}$",
    )

    # Coordinates (Spain geographic bounds)
    latitude: Optional[float] = Field(
        None,
        description="Latitude coordinate",
        ge=36.0,  # Spain southern bound
        le=43.8,  # Spain northern bound
    )
    longitude: Optional[float] = Field(
        None,
        description="Longitude coordinate",
        ge=-9.3,  # Spain western bound
        le=4.3,  # Spain eastern bound
    )

    # Contact information
    phone: Optional[str] = Field(
        None,
        description="Contact phone number",
        max_length=20,
    )
    email: Optional[str] = Field(
        None,
        description="Contact email address",
        max_length=100,
    )

    # Metadata for traceability
    raw_id: Optional[str] = Field(
        None,
        description="Original ID from source system (for traceability)",
        max_length=100,
    )
    normalized_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when normalization occurred (UTC)",
    )

    @field_validator("city", "province")
    @classmethod
    def uppercase_location(cls, v: Optional[str]) -> Optional[str]:
        """Ensure city and province are in UPPERCASE for consistency."""
        return v.upper() if v else None

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        """Clean station name by stripping extra whitespace."""
        return " ".join(v.strip().split())

    @field_validator("source_system")
    @classmethod
    def lowercase_source(cls, v: str) -> str:
        """Ensure source_system is lowercase."""
        return v.lower()

    class Config:
        json_schema_extra = {
            "example": {
                "station_id": "CAT_001",
                "name": "ITV Barcelona Nord",
                "address": "Carrer de la Indústria 123",
                "city": "BARCELONA",
                "province": "BARCELONA",
                "postal_code": "08025",
                "latitude": 41.3851,
                "longitude": 2.1734,
                "phone": "+34 932 123 456",
                "email": "info@itvbarcelona.cat",
                "source_system": "catalunya",
                "raw_id": "BCN-ITV-001",
                "normalized_at": "2026-02-17T10:30:00Z",
            }
        }
