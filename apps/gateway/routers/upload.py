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

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request, status

from apps.gateway.schemas import RawIngestionMessage
from apps.gateway.fanout import split_payload_by_station
from domain.synthetic_data_generator import SyntheticDataGenerator, InvalidSyntheticDataGenerator

router = APIRouter(prefix="/api/v1", tags=["injection"])


@router.post("/inject/synthetic/{source}")
async def inject_synthetic_data(
    request: Request,
    source: str,
    count: int = Query(10, ge=1, le=10000),
    error_rate: float = Query(0.0, ge=0.0, le=1.0),
    include_errors: list[str] = Query(default=[]),
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

        # Preparar metadata de inyección (será transportada en el mensaje)
        injection_metadata = {
            "generated_count": count,
            "error_rate": error_rate,
            "error_types": include_errors,
        }

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
                injection_type="synthetic",
                injection_metadata=injection_metadata,
            )

            await rabbitmq_client.publish(
                message=station_message.model_dump(mode="json"),
                exchange_name="raw_data",
                routing_key="itv_stations",
            )

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


@router.post("/inject/synthetic-mixed/{source}")
async def inject_synthetic_mixed_data(
    request: Request,
    source: str,
    count: int = Query(10, ge=1, le=10000),
    error_rate: float = Query(0.0, ge=0.0, le=1.0),
    error_types: list[str] = Query(default=[]),
) -> dict[str, Any]:
    """
    Inyecta datos sintéticos MEZCLADOS (válidos + inválidos) para testing.

    Genera un lote combinando estaciones válidas e inválidas según error_rate:
    - Si count=100 y error_rate=0.1: genera 90 válidas + 10 inválidas
    - Todas se publican a raw_data para procesamiento
    - Los datos válidos llegan a normalized_data
    - Los datos inválidos llegan a rejected_data (trazados en ingestion_log)

    Path Parameters:
        source: 'catalunya', 'valencia', 'galicia'

    Query Parameters:
        count: Total de estaciones a generar (1-10000, default 10)
        error_rate: Porcentaje de error [0.0-1.0] (default 0.0)
        error_types: Tipos de error específicos a inyectar (opcional)
            Tipos disponibles:
            - 'invalid_postal_code'
            - 'invalid_province'
            - 'coordinates_outside_spain'
            - 'coordinates_outside_province'
            - 'invalid_email'
            - 'missing_contact_fields'
            - 'oversized_name'
            - 'undersized_station_id'
            - 'malformed_coordinates'
            - 'invalid_city_not_in_province'

    Example:
        POST /api/v1/inject/synthetic-mixed/catalunya?count=100&error_rate=0.1
        → Genera 90 válidas + 10 inválidas

    Returns: {
        "status": "accepted",
        "injection_type": "synthetic-mixed",
        "source": "catalunya",
        "message_id": "uuid",
        "total_count": 100,
        "valid_count": 90,
        "invalid_count": 10,
        "error_rate_requested": 0.1,
        "error_types": [],
        "queued_messages": 100,
        "timestamp": "2026-05-17T10:35:00Z"
    }
    """
    # Validar source
    valid_sources = ["catalunya", "valencia", "galicia"]
    if source not in valid_sources:
        raise HTTPException(
            status_code=400, detail=f"Invalid source: {source}. Must be one of: {valid_sources}"
        )

    from typing import Literal
    from math import ceil, floor

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
        # Coerce Query param types (FastAPI Query can pass special objects when called directly)
        if not isinstance(error_types, list):
            error_types = []

        # Calcular distribución: válidas vs inválidas
        valid_count = ceil(count * (1 - error_rate))
        invalid_count = floor(count * error_rate)

        # Si error_rate es exactamente 0, ambos tipos de cálculo darían resultados que no suman count
        # Ajustar para asegurar que valid_count + invalid_count = count
        if valid_count + invalid_count != count:
            if error_rate > 0:
                invalid_count = count - valid_count
            else:
                valid_count = count

        # Generar datos sintéticos válidos
        valid_payload: dict[str, Any] = {}
        if valid_count > 0:
            valid_payload = SyntheticDataGenerator.generate_stations(
                source=source_literal,
                count=valid_count,
                error_rate=0.0,  # Sin errores
            )

        # Generar datos sintéticos inválidos
        invalid_payload: dict[str, Any] = {}
        if invalid_count > 0:
            invalid_payload = InvalidSyntheticDataGenerator.generate_invalid_stations(
                source=source_literal,
                count=invalid_count,
                error_types=error_types if error_types else None,
            )

        # Combinar ambos lotes
        if source == "valencia":
            combined_stations = (
                valid_payload.get("estaciones", []) + invalid_payload.get("estaciones", [])
            )
            combined_payload = {"estaciones": combined_stations}
        else:
            combined_stations = (
                valid_payload.get("stations", []) + invalid_payload.get("stations", [])
            )
            combined_payload = {"stations": combined_stations}

        # Generar message_id único para este lote
        message_id = str(uuid4())

        # Preparar metadata de inyección (será transportada en el mensaje)
        injection_metadata = {
            "total_count": count,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "error_rate": error_rate,
            "error_types": error_types,
        }

        # Fan-out en estaciones individuales
        station_payloads = split_payload_by_station(
            source=source_literal,
            data_format="json",
            payload=combined_payload,  # type: ignore[arg-type]
        )

        if not station_payloads:
            raise HTTPException(status_code=400, detail="No station records generated")

        # Publicar a RabbitMQ
        for idx, station_payload in enumerate(station_payloads, start=1):
            station_message = RawIngestionMessage(
                message_id=str(uuid4()),
                parent_message_id=message_id,
                station_sequence=idx,
                total_stations=len(station_payloads),
                source=source_literal,
                payload=station_payload,
                format="json",
                injection_type="synthetic-mixed",
                injection_metadata=injection_metadata,
            )

            await rabbitmq_client.publish(
                message=station_message.model_dump(mode="json"),
                exchange_name="raw_data",
                routing_key="itv_stations",
            )

        return {
            "status": "accepted",
            "injection_type": "synthetic-mixed",
            "message_id": message_id,
            "source": source,
            "total_count": count,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "error_rate_requested": error_rate,
            "error_types": error_types,
            "queued_messages": len(station_payloads),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating synthetic mixed data: {str(e)}"
        )


@router.post("/files/upload/{source}")
async def upload_file(
    request: Request,
    source: str,
    file: UploadFile = File(...),
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

        # Preparar metadata de inyección (será transportada en el mensaje)
        injection_metadata = {
            "filename": file.filename,
            "size_bytes": file_size,
            "format": detected_format,
        }

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
                injection_type="file",
                injection_metadata=injection_metadata,
            )

            await rabbitmq_client.publish(
                message=station_message.model_dump(mode="json"),
                exchange_name="raw_data",
                routing_key="itv_stations",
            )

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
