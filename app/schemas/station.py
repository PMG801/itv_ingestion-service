from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class EstacionResponse(BaseModel):
    """
    Modelo de respuesta para una estación ITV.
    Basado en el JSON requerido por el frontend.
    """
    nombre: str
    direccion: Optional[str] = None
    localidad: str
    codigo_postal: Optional[str] = None
    provincia: str
    descripcion: Optional[str] = None
    tipo: Optional[str] = None
    latitud: float
    longitud: float
    
    # Configuración para compatibilidad con diccionarios/objetos si fuera necesario
    model_config = ConfigDict(from_attributes=True)

class ErrorResponse(BaseModel):
    detail: str
