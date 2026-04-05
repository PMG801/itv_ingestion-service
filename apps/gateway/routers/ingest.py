"""
Ingestion Router - HTTP endpoint for data ingestion.

Provides REST API endpoint to receive raw data from external sources,
wrap it in a standardized message format, and publish to RabbitMQ for
asynchronous processing.
"""

import logging
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status

from apps.gateway.schemas import (
    IngestRequest,
    IngestResponse,
    RawIngestionMessage,
    ErrorResponse,
)
from apps.gateway.fanout import split_payload_by_station

logger = logging.getLogger(__name__)

router = APIRouter()

# Valid data sources
VALID_SOURCES: list[Literal["catalunya", "valencia", "galicia"]] = [
    "catalunya",
    "valencia",
    "galicia",
]


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
    source_lower: Literal["catalunya", "valencia", "galicia"] = source

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
        station_payloads = split_payload_by_station(
            source=source_lower,
            data_format=ingest_request.format,
            payload=ingest_request.payload,
        )

        if not station_payloads:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payload does not contain any station records",
            )

        batch_message_id = str(uuid4())

        logger.info(
            f"Processing ingestion request: source={source_lower}, "
            f"format={ingest_request.format}, batch_message_id={batch_message_id}, "
            f"stations={len(station_payloads)}"
        )

        for idx, station_payload in enumerate(station_payloads, start=1):
            station_message = RawIngestionMessage(
                message_id=str(uuid4()),
                parent_message_id=batch_message_id,
                station_sequence=idx,
                total_stations=len(station_payloads),
                source=source_lower,
                payload=station_payload,
                format=ingest_request.format,
            )

            await rabbitmq_client.publish(
                message=station_message.model_dump(mode="json"),
                exchange_name="raw_data",
                routing_key="itv_stations",
            )

        logger.info(
            f"Successfully published {len(station_payloads)} station messages "
            f"for batch {batch_message_id} from source {source_lower}"
        )

        # Return 202 Accepted with message_id for tracking
        return IngestResponse(
            message_id=batch_message_id,
            status="accepted",
            message=f"Data from {source_lower} queued for processing",
            queued_messages=len(station_payloads),
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
