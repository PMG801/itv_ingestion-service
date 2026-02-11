from pydantic import BaseModel, ConfigDict
from typing import Optional

class ProvinciaResponse(BaseModel):
    """
    Modelo de respuesta para una Provincia.
    """
    id: int
    nombre: str
    
    model_config = ConfigDict(from_attributes=True)

class LocalidadResponse(BaseModel):
    """
    Modelo de respuesta para una Localidad.
    """
    id: int
    nombre: str
    provincia_id: int
    
    model_config = ConfigDict(from_attributes=True)
