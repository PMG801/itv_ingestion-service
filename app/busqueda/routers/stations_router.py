"""  
Router de búsqueda de estaciones ITV.

Este módulo proporciona los endpoints para buscar estaciones ITV
aplicando diversos filtros geográficos y de tipo.

Endpoints:
- GET /api/estaciones - Buscar estaciones con filtros opcionales
"""

from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional
from app.schemas.station import EstacionResponse, ErrorResponse
from app.db.search_queries import search_stations
import logging

# Configurar router con prefijo y tags para documentación automática
router = APIRouter(
    prefix="/api/estaciones",
    tags=["Búsqueda de Estaciones"]
)

logger = logging.getLogger(__name__)

@router.get("", 
    response_model=List[EstacionResponse],
    responses={
        400: {"model": ErrorResponse, "description": "Parámetros de búsqueda inválidos."},
        500: {"model": ErrorResponse, "description": "Error interno del servidor o base de datos."}
    },
    summary="Buscar estaciones ITV"
)
async def get_estaciones(
    localidad: Optional[str] = Query(None, description="Filtra por nombre de localidad (coincidencia parcial)"),
    codigo_postal: Optional[str] = Query(None, description="Filtra por código postal (prefijo o exacto)"),
    provincia: Optional[str] = Query(None, description="Filtra por nombre de provincia (coincidencia parcial)"),
    tipo: Optional[str] = Query(None, description="Filtra por tipo de estación (ej. 'ITV', 'Móvil')")
):
    """
    **Busca estaciones ITV** en el almacén de datos filtrando por los criterios especificados.
    
    Este endpoint permite buscar estaciones aplicando múltiples filtros de forma combinada.
    Todos los filtros son opcionales y se aplican con lógica AND (deben cumplirse todos).
    
    Parámetros de búsqueda:
    - **localidad**: Búsqueda parcial por nombre de localidad (case-insensitive)
    - **codigo_postal**: Búsqueda por código postal (prefijo o exacto)
    - **provincia**: Búsqueda parcial por nombre de provincia (case-insensitive)
    - **tipo**: Tipo de estación ("fija", "movil", "otros")
    
    Respuesta:
    - Lista de estaciones con sus datos completos incluyendo geolocalización (lat/long)
    - Si no se encuentran resultados, devuelve lista vacía []
    - Si no se especifican filtros, devuelve TODAS las estaciones (usar con precaución)
    
    Raises:
        HTTPException 500: Error interno del servidor o base de datos
    
    Returns:
        List[EstacionResponse]: Lista de estaciones que cumplen los criterios
    """
    try:
        # Log de la petición para auditoria y debug
        logger.info(f"Recibida petición de búsqueda: loc={localidad}, cp={codigo_postal}, prov={provincia}, tipo={tipo}")
        
        # Ejecutar búsqueda en la base de datos con los filtros especificados
        resultados = await search_stations(
            localidad=localidad,
            codigo_postal=codigo_postal,
            provincia=provincia,
            tipo=tipo
        )
        
        # Devolver resultados (FastAPI los serializa automáticamente a JSON)
        return resultados
    
    except Exception as e:
        # Log del error para debugging
        logger.error(f"Error en endpoint get_estaciones: {str(e)}")
        # Devolver error genérico al cliente (no exponer detalles internos)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar la búsqueda. Por favor contacte al administrador."
        )
