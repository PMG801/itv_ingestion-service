from fastapi import APIRouter, HTTPException, status
from typing import List
from app.schemas.location import ProvinciaResponse
from app.db.search_queries import get_all_provinces
import logging

router = APIRouter(
    prefix="/api/provincias",
    tags=["Información Geográfica"]
)

logger = logging.getLogger(__name__)

@router.get("", 
    response_model=List[ProvinciaResponse],
    summary="Obtener todas las provincias"
)
async def list_provincias():
    """
    Devuelve un listado de **todas las provincias** registradas en el sistema.
    Útil para poblar selectores en el frontend.
    """
    try:
        provincias = await get_all_provinces()
        return provincias
    except Exception as e:
        logger.error(f"Error en endpoint list_provincias: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener las provincias."
        )
