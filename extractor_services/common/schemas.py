"""
Schemas compartidos entre todos los servicios extractores.
Define el formato JSON estandarizado que todos deben seguir.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TipoEstacion(str, Enum):
    """Tipos válidos de estación ITV"""
    ESTACION_FIJA = "estacion_fija"
    ESTACION_MOVIL = "estacion_movil"
    OTROS = "otros"


class EstacionExtraida(BaseModel):
    """
    Modelo de una estación ITV extraída y transformada.
    Este es el formato estandarizado que todos los extractores deben producir.
    """
    nombre: str = Field(..., description="Nombre de la estación")
    tipo: TipoEstacion = Field(default=TipoEstacion.ESTACION_FIJA, description="Tipo de estación")
    direccion: Optional[str] = Field(None, description="Dirección completa")
    codigo_postal: Optional[str] = Field(None, description="Código postal (5 dígitos)")
    localidad: str = Field(..., description="Nombre del municipio/localidad")
    provincia: str = Field(..., description="Nombre de la provincia")
    latitud: float = Field(..., ge=-90, le=90, description="Latitud WGS84")
    longitud: float = Field(..., ge=-180, le=180, description="Longitud WGS84")
    descripcion: Optional[str] = Field(None, description="Descripción adicional")
    horario: Optional[str] = Field(None, description="Horario de atención")
    contacto: Optional[str] = Field(None, description="Email o teléfono de contacto")
    url: Optional[str] = Field(None, description="URL del sitio web")

    class Config:
        json_schema_extra = {
            "example": {
                "nombre": "Estación ITV de Valencia",
                "tipo": "estacion_fija",
                "direccion": "Av. del Puerto 123",
                "codigo_postal": "46001",
                "localidad": "Valencia",
                "provincia": "Valencia",
                "latitud": 39.4699,
                "longitud": -0.3763,
                "descripcion": None,
                "horario": "L-V 8:00-20:00",
                "contacto": "info@itv.es",
                "url": "https://sitval.com"
            }
        }


class RegistroRechazado(BaseModel):
    """Información sobre un registro que fue rechazado durante la transformación"""
    registro: int = Field(..., description="Número de registro en el archivo fuente")
    nombre: Optional[str] = Field(None, description="Nombre o identificador del registro")
    razon: str = Field(..., description="Razón del rechazo")


class EstadisticasExtraccion(BaseModel):
    """Estadísticas del proceso de extracción"""
    total_raw: int = Field(..., description="Total de registros en el archivo fuente")
    transformados: int = Field(..., description="Registros transformados exitosamente")
    rechazados: int = Field(..., description="Registros rechazados")


class PayloadExtraccion(BaseModel):
    """
    Payload completo que envía un servicio extractor a la API central.
    Este es el contrato entre los extractores y la API central.
    """
    source: str = Field(..., description="Identificador de la fuente (VAL, CAT, GAL)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Momento de la extracción")
    estaciones: List[EstacionExtraida] = Field(default_factory=list, description="Lista de estaciones extraídas")
    rechazados: List[RegistroRechazado] = Field(default_factory=list, description="Lista de registros rechazados")
    stats: EstadisticasExtraccion = Field(..., description="Estadísticas del proceso")

    class Config:
        json_schema_extra = {
            "example": {
                "source": "VAL",
                "timestamp": "2024-12-23T10:30:00Z",
                "estaciones": [
                    {
                        "nombre": "Estación ITV de Valencia",
                        "tipo": "estacion_fija",
                        "direccion": "Av. del Puerto 123",
                        "codigo_postal": "46001",
                        "localidad": "Valencia",
                        "provincia": "Valencia",
                        "latitud": 39.4699,
                        "longitud": -0.3763,
                        "horario": "L-V 8:00-20:00"
                    }
                ],
                "rechazados": [
                    {
                        "registro": 5,
                        "nombre": "Estación Inválida",
                        "razon": "Código postal inválido"
                    }
                ],
                "stats": {
                    "total_raw": 50,
                    "transformados": 49,
                    "rechazados": 1
                }
            }
        }


# ===== RESPUESTAS DE LA API CENTRAL =====

class IngestResponse(BaseModel):
    """Respuesta de la API central al recibir datos de un extractor"""
    status: str = Field(..., description="Estado: 'success', 'partial', 'error'")
    source: str = Field(..., description="Fuente procesada")
    recibidos: int = Field(..., description="Estaciones recibidas")
    insertados: int = Field(..., description="Estaciones insertadas correctamente")
    duplicados_detectados: int = Field(default=0, description="Duplicados detectados y omitidos")
    errores_insercion: int = Field(default=0, description="Errores durante inserción en BD")
    mensaje: str = Field(..., description="Mensaje descriptivo")
    logs: Optional[dict] = Field(default=None, description="Logs detallados con errores y duplicados")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "source": "VAL",
                "recibidos": 49,
                "insertados": 47,
                "duplicados_detectados": 2,
                "errores_insercion": 0,
                "mensaje": "Carga completada: 47 estaciones insertadas, 2 duplicados omitidos",
                "logs": {"stats": {"total": 49, "exitosos": 47, "fallidos": 2}, "logs": []}
            }
        }


# ===== RESPUESTAS DE LOS EXTRACTORES =====

class ExtractorHealthResponse(BaseModel):
    """Respuesta del endpoint de salud de un extractor"""
    service: str
    status: str
    version: str
    source_file: str


class ExtractorPreviewResponse(BaseModel):
    """Respuesta del endpoint de preview (sin enviar a API central)"""
    status: str
    source: str
    payload: PayloadExtraccion
    mensaje: str


class ExtractorResponse(BaseModel):
    """Respuesta del endpoint de extracción completa"""
    status: str
    source: str
    extraidos: int
    enviado_a_central: bool
    respuesta_central: Optional[IngestResponse] = None
    error: Optional[str] = None
