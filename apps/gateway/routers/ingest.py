"""
Ingestion Router - HTTP endpoint for data ingestion.

Provides REST API endpoint to receive raw data from external sources,
wrap it in a standardized message format, and publish to RabbitMQ for
asynchronous processing.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse

from apps.gateway.schemas import (
    IngestRequest,
    IngestResponse,
    RawIngestionMessage,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Valid data sources
VALID_SOURCES = ["catalunya", "valencia", "galicia"]


@router.post(
    "/ingest/{source}",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest raw data from external source",
    description=(
        "Receives raw data from external ITV data sources (Catalunya, Valencia, Galicia), "
        "wraps it in a standardized message format, and publishes it to RabbitMQ for "
        "asynchronous processing by the normalizer worker."
    ),
    responses={
        202: {
            "description": "Data accepted and queued for processing",
            "model": IngestResponse,
        },
        400: {
            "description": "Invalid request data or unsupported source",
            "model": ErrorResponse,
        },
        503: {
            "description": "RabbitMQ connection unavailable",
            "model": ErrorResponse,
        },
    },
)
async def ingest_data(
    source: Literal["catalunya", "valencia", "galicia"],
    request: Request,
    ingest_request: IngestRequest,
) -> IngestResponse:
    """
    Ingest raw data from external source.
    
    Receives data from external ITV APIs, validates the source, wraps it
    in a RawIngestionMessage envelope with traceability metadata, and
    publishes it to the raw_data exchange in RabbitMQ.
    
    Args:
        source: Data source identifier (catalunya, valencia, galicia).
        request: FastAPI request object (for accessing app state).
        ingest_request: Request body containing payload and format.
        
    Returns:
        IngestResponse: Confirmation with message_id for tracking.
        
    Raises:
        HTTPException 400: If source is invalid or request is malformed.
        HTTPException 503: If RabbitMQ is unavailable.
    """
    # Normalize source to lowercase
    source_lower = source.lower()
    
    # Validate source
    if source_lower not in VALID_SOURCES:
        logger.warning(f"Invalid source attempted: {source}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source '{source}'. Valid sources: {', '.join(VALID_SOURCES)}",
        )
    
    # Check RabbitMQ connection
    if not hasattr(request.app.state, "rabbitmq"):
        logger.error("RabbitMQ client not initialized in app state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Messaging service unavailable",
        )
    
    rabbitmq_client = request.app.state.rabbitmq
    
    if not rabbitmq_client.is_connected:
        logger.error("RabbitMQ client not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Messaging service unavailable - not connected",
        )
    
    try:
        # Create RawIngestionMessage with auto-generated message_id and timestamp
        raw_message = RawIngestionMessage(
            source=source_lower,
            payload=ingest_request.payload,
            format=ingest_request.format,
        )
        
        logger.info(
            f"Processing ingestion request: source={source_lower}, "
            f"format={ingest_request.format}, message_id={raw_message.message_id}"
        )
        
        # Publish to RabbitMQ
        # Exchange: raw_data (topic)
        # Routing key: itv_stations (routes to raw_data.itv_stations queue)
        await rabbitmq_client.publish(
            message=raw_message.model_dump(mode="json"),
            exchange_name="raw_data",
            routing_key="itv_stations",
        )
        
        logger.info(
            f"Successfully published message {raw_message.message_id} "
            f"from source {source_lower} to RabbitMQ"
        )
        
        # Return 202 Accepted with message_id for tracking
        return IngestResponse(
            message_id=raw_message.message_id,
            status="accepted",
            message=f"Data from {source_lower} queued for processing",
        )
        
    except Exception as e:
        logger.error(
            f"Failed to publish message from source {source_lower}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue message: {str(e)}",
        )


@router.get(
    "/sources",
    summary="List valid data sources",
    description="Returns the list of valid data sources that can be ingested",
    response_model=dict,
)
async def list_sources():
    """
    List valid ingestion sources.
    
    Returns:
        dict: List of valid source identifiers.
    """
    return {
        "sources": VALID_SOURCES,
        "description": "Valid ITV data sources for ingestion",
    }
