"""
Gateway API schemas - Pydantic models for request/response validation.

Defines data contracts for the ingestion API endpoints, including message
formats and response models.
"""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

PayloadDict = dict[str, object]


class RawIngestionMessage(BaseModel):
    """
    Raw ingestion message format for data entering the system.
    
    This model represents the envelope for raw data from external sources
    before any processing or normalization. It captures the original payload
    along with metadata for traceability.
    
    Attributes:
        message_id: Unique identifier for message tracing (auto-generated UUID).
        source: Data source identifier (catalunya, valencia, galicia).
        payload: Raw data as received (JSON dict or string for XML/CSV).
        format: Data format of the payload (json, xml, csv).
        ingested_at: Timestamp when data entered the gateway (auto-generated UTC).
    """

    message_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique message identifier for traceability",
    )
    source: Literal["catalunya", "valencia", "galicia"] = Field(
        ...,
        description="Data source identifier",
        examples=["catalunya", "valencia", "galicia"],
    )
    payload: PayloadDict | str = Field(
        ...,
        description="Raw data payload (JSON object or string for XML/CSV)",
    )
    format: Literal["json", "xml", "csv"] = Field(
        ...,
        description="Data format of the payload",
        examples=["json", "xml", "csv"],
    )
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Ingestion timestamp (UTC)",
    )

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Ensure source is lowercase and valid."""
        return v.lower()

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Ensure format is lowercase and valid."""
        return v.lower()

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "source": "catalunya",
                "payload": {
                    "stations": [
                        {
                            "id": "CT-001",
                            "name": "ITV Barcelona Nord",
                            "address": "Carrer Example 123",
                        }
                    ]
                },
                "format": "json",
                "ingested_at": "2026-02-17T10:30:00Z",
            }
        }


class IngestRequest(BaseModel):
    """
    Request body for ingestion endpoint.
    
    Attributes:
        payload: Raw data from external source (any valid JSON).
        format: Data format (defaults to json, can be xml or csv).
    """

    payload: PayloadDict | str = Field(
        ...,
        description="Raw data to ingest",
    )
    format: Literal["json", "xml", "csv"] = Field(
        default="json",
        description="Format of the payload",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "payload": {
                    "stations": [
                        {
                            "id": "CT-001",
                            "name": "ITV Barcelona Nord",
                        }
                    ]
                },
                "format": "json",
            }
        }


class IngestResponse(BaseModel):
    """
    Response model for successful ingestion.
    
    Attributes:
        message_id: Unique identifier for tracking the ingested message.
        status: Processing status (always 'accepted' for 202 responses).
        timestamp: Server timestamp when request was processed.
        message: Human-readable status message.
    """

    message_id: str = Field(
        ...,
        description="Unique message identifier for tracking",
    )
    status: str = Field(
        default="accepted",
        description="Message status",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Response timestamp (UTC)",
    )
    message: str = Field(
        default="Message queued for processing",
        description="Status message",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "accepted",
                "timestamp": "2026-02-17T10:30:00Z",
                "message": "Message queued for processing",
            }
        }


class ErrorResponse(BaseModel):
    """
    Error response model for failed requests.
    
    Attributes:
        error: Error type or category.
        detail: Detailed error message.
        timestamp: Error occurrence timestamp.
    """

    error: str = Field(
        ...,
        description="Error type",
    )
    detail: str = Field(
        ...,
        description="Detailed error message",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Error timestamp (UTC)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "error": "InvalidSource",
                "detail": "Source 'invalid' is not supported. Valid sources: catalunya, valencia, galicia",
                "timestamp": "2026-02-17T10:30:00Z",
            }
        }
