"""
Upload Router para inyección de datos (archivos y sintéticos).

Proporciona endpoints para:
1. Carga de archivos (CSV, JSON, XML)
2. Inyección de datos sintéticos

Todos los datos se publican a raw_data exchange para procesamiento asíncrono.
"""

from typing import Any
from uuid import uuid4
from datetime import datetime, timezone
import json

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_session
from apps.gateway.schemas import RawIngestionMessage
from apps.gateway.fanout import split_payload_by_station
from domain.synthetic_data_generator import SyntheticDataGenerator
from domain.itv_stations.models import IngestionLog

router = APIRouter(prefix="/api/v1", tags=["injection"])


@router.post("/inject/synthetic/{source}")
async def inject_synthetic_data(
    request: Request,
    source: str,
    count: int = Query(10, ge=1, le=10000),
    error_rate: float = Query(0.0, ge=0.0, le=1.0),
    include_errors: list[str] = Query(default=[]),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Inyecta datos sintéticos para benchmarking.

    Genera estaciones ITV realistas y las publica a raw_data queue para procesamiento.

    Path Parameters:
        source: 'catalunya', 'valencia', 'galicia'

    Query Parameters:
        count: Número de estaciones a generar (1-10000, default 10)

    Example:
        POST /api/v1/inject/synthetic/catalunya?count=50

    Query Parameters:
        error_rate: Probability of injecting an error (0.0-1.0, default 0.0)
        include_errors: Error types allowed in the synthetic generator

    Returns: {
        "status": "accepted",
        "injection_type": "synthetic",
        "source": "catalunya",
        "message_ids": ["uuid1", "uuid2", ...],
        "count": 50,
        "timestamp": "2026-03-20T12:00:00+00:00"
    }
    """
    # Validar source
    valid_sources = ["catalunya", "valencia", "galicia"]
    if source not in valid_sources:
        raise HTTPException(
            status_code=400, detail=f"Invalid source: {source}. Must be one of: {valid_sources}"
        )

    if not isinstance(error_rate, (int, float)):
        error_rate = 0.0
    if not isinstance(include_errors, list):
        include_errors = []

    valid_error_types = {
        "invalid_coordinates",
        "missing_field",
        "duplicate",
        "malformed_phone",
    }
    invalid_error_types = [error_type for error_type in include_errors if error_type not in valid_error_types]
    if invalid_error_types:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid error types: {invalid_error_types}. "
                f"Must be one of: {sorted(valid_error_types)}"
            ),
        )

    from typing import Literal

    source_literal: Literal["catalunya", "valencia", "galicia"] = source  # type: ignore[assignment]

    if not hasattr(request.app.state, "rabbitmq"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Messaging service unavailable",
        )

    rabbitmq_client = request.app.state.rabbitmq
    if not rabbitmq_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Messaging service unavailable - not connected",
        )

    try:
        # Generar datos sintéticos
        payload_dict = SyntheticDataGenerator.generate_stations(
            source=source_literal,
            count=count,
            error_rate=error_rate,
            include_errors=include_errors,
        )

        # Generar message_id único para este lote
        message_id = str(uuid4())

        # Crear IngestionLog para tracking
        log_entry = IngestionLog(
            message_id=message_id,
            domain="itv_stations",
            source_system=source_literal,
            status="processing",
        )
        log_entry.set_injection_type(
            "synthetic",
            {
                "generated_count": count,
                "error_rate": error_rate,
                "error_types": include_errors,
            },
        )
        session.add(log_entry)
        station_payloads = split_payload_by_station(
            source=source_literal,
            data_format="json",
            payload=payload_dict,  # type: ignore[arg-type]
        )
        if not station_payloads:
            raise HTTPException(status_code=400, detail="No station records generated")

        for idx, station_payload in enumerate(station_payloads, start=1):
            station_message = RawIngestionMessage(
                message_id=str(uuid4()),
                parent_message_id=message_id,
                station_sequence=idx,
                total_stations=len(station_payloads),
                source=source_literal,
                payload=station_payload,
                format="json",
            )

            await rabbitmq_client.publish(
                message=station_message.model_dump(mode="json"),
                exchange_name="raw_data",
                routing_key="itv_stations",
            )

        await session.commit()

        return {
            "status": "accepted",
            "injection_type": "synthetic",
            "message_id": message_id,
            "source": source,
            "count": count,
            "error_rate": error_rate,
            "include_errors": include_errors,
            "queued_messages": len(station_payloads),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating synthetic data: {str(e)}")


@router.post("/files/upload/{source}")
async def upload_file(
    request: Request,
    source: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """
    Carga un archivo (CSV, JSON, XML) para ingesta.

    Valida el formato, normaliza el nombre, y publica a raw_data queue.

    Path Parameters:
        source: 'catalunya', 'valencia', 'galicia'

    Form Data:
        file: Archivo a cargar (MIME type: application/json, text/xml, text/csv)

    Returns: {
        "status": "accepted",
        "injection_type": "file",
        "message_id": "uuid",
        "filename": "stations.json",
        "size_bytes": 45621,
        "source": "catalunya",
        "timestamp": "2026-03-20T12:00:00+00:00"
    }

    HTTP Status:
        202: ACCEPTED - Archivo encolado para procesamiento
        400: BAD REQUEST - Formato no válido
        413: PAYLOAD TOO LARGE - Archivo > 50MB
        415: UNSUPPORTED MEDIA TYPE - Tipo MIME no soportado
    """
    # Validar source
    valid_sources = ["catalunya", "valencia", "galicia"]
    if source not in valid_sources:
        raise HTTPException(
            status_code=400, detail=f"Invalid source: {source}. Must be one of: {valid_sources}"
        )

    from typing import Literal as LiteralType

    source_literal: LiteralType["catalunya", "valencia", "galicia"] = source  # type: ignore[assignment]

    if not hasattr(request.app.state, "rabbitmq"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Messaging service unavailable",
        )

    rabbitmq_client = request.app.state.rabbitmq
    if not rabbitmq_client.is_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Messaging service unavailable - not connected",
        )

    # Validar tamaño
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    file_size = 0

    # Validar tipo MIME
    valid_mimes = {
        "application/json": "json",
        "text/json": "json",
        "text/xml": "xml",
        "application/xml": "xml",
        "text/csv": "csv",
        "text/plain": "csv",  # Permitir CSV como text/plain
    }

    detected_format: str = valid_mimes.get(file.content_type, "")  # type: ignore[assignment]

    if not detected_format:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. "
            f"Supported: {list(valid_mimes.keys())}",
        )

    try:
        # Leer contenido del archivo
        contents = await file.read()
        file_size = len(contents)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size} bytes. Max: {MAX_FILE_SIZE} bytes",
            )

        payload_str = contents.decode("utf-8")

        # Validar que es JSON/XML/CSV válido
        if detected_format == "json":
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
        elif detected_format == "xml":
            # Validación básica XML (no parsear completamente)
            if not payload_str.strip().startswith("<"):
                raise HTTPException(status_code=400, detail="Invalid XML: must start with <")
            payload = payload_str
        else:  # CSV
            # Validación básica CSV
            lines = payload_str.strip().split("\n")
            if len(lines) < 2:
                raise HTTPException(
                    status_code=400, detail="Invalid CSV: must have header and at least one row"
                )
            payload = payload_str

        # Generar message_id único
        message_id = str(uuid4())

        # Crear IngestionLog para tracking
        log_entry = IngestionLog(
            message_id=message_id,
            domain="itv_stations",
            source_system=source_literal,
            status="processing",
        )
        log_entry.set_injection_type(
            "file",
            {
                "filename": file.filename,
                "size_bytes": file_size,
                "format": detected_format,
            },
        )
        session.add(log_entry)
        station_payloads = split_payload_by_station(
            source=source_literal,
            data_format=detected_format,  # type: ignore[arg-type]
            payload=payload,  # type: ignore[arg-type]
        )
        if not station_payloads:
            raise HTTPException(status_code=400, detail="Uploaded payload has no station records")

        for idx, station_payload in enumerate(station_payloads, start=1):
            station_message = RawIngestionMessage(
                message_id=str(uuid4()),
                parent_message_id=message_id,
                station_sequence=idx,
                total_stations=len(station_payloads),
                source=source_literal,
                payload=station_payload,
                format=detected_format,  # type: ignore[arg-type]
            )

            await rabbitmq_client.publish(
                message=station_message.model_dump(mode="json"),
                exchange_name="raw_data",
                routing_key="itv_stations",
            )

        await session.commit()

        return {
            "status": "accepted",
            "injection_type": "file",
            "message_id": message_id,
            "filename": file.filename,
            "size_bytes": file_size,
            "format": detected_format,
            "source": source,
            "queued_messages": len(station_payloads),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    finally:
        await file.close()
