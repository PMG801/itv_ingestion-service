# Common module for extractor services
from .schemas import (
    TipoEstacion,
    EstacionExtraida,
    RegistroRechazado,
    EstadisticasExtraccion,
    PayloadExtraccion,
    IngestResponse,
    ExtractorHealthResponse,
    ExtractorPreviewResponse,
    ExtractorResponse
)
from .config import ExtractorSettings, ValenciaSettings, CatalunyaSettings, GaliciaSettings
from .client import CentralAPIClient, create_client

# Normalizers
from .normalizers import (
    normalize_text,
    normalize_estacion_name,
    normalize_schedule,
    normalize_codigo_postal,
    normalize_tipo_estacion,
    normalize_direccion,
    capitalize_provincia,
    is_valid_email,
    separate_email_and_url,
    parse_coordinates,
    parse_single_coordinate,
    find_column,
    safe_get,
    make_code,
    DIAS_MAPPING,
)

# Spanish locations
from .spanish_locations import (
    PROVINCIAS_VALIDAS,
    PROVINCIA_ALIASES,
    RANGOS_CODIGOS_POSTALES,
    RANGOS_COORDENADAS_PROVINCIAS,
    RANGO_COORDENADAS_ESPANA,
    normalizar_provincia,
    obtener_provincia_por_codigo_postal,
    validar_codigo_postal,
    obtener_rango_coordenadas_provincia,
)

# Validators
from .validators import (
    validar_provincia,
    normalizar_municipio,
    validar_ubicacion_por_codigo_postal,
    validar_coordenadas,
    validar_campos_obligatorios,
    validar_estacion_completa,
    log_estadisticas_validacion,
)

# Duplicate detector
from .duplicate_detector import (
    DetectorDuplicados,
    DuplicateFilter,
    detectar_duplicados,
    CriterioDuplicado,
    CriterioNombreCodigoPostal,
    CriterioNombreDireccion,
    CriterioCoordenadas,
    calcular_distancia_haversine,
    normalizar_para_comparacion,
    extraer_nombre_base,
)

__all__ = [
    # Schemas
    "TipoEstacion",
    "EstacionExtraida",
    "RegistroRechazado",
    "EstadisticasExtraccion",
    "PayloadExtraccion",
    "IngestResponse",
    "ExtractorHealthResponse",
    "ExtractorPreviewResponse",
    "ExtractorResponse",
    # Config
    "ExtractorSettings",
    "ValenciaSettings",
    "CatalunyaSettings",
    "GaliciaSettings",
    # Client
    "CentralAPIClient",
    "create_client",
    # Normalizers
    "normalize_text",
    "normalize_estacion_name",
    "normalize_schedule",
    "normalize_codigo_postal",
    "normalize_tipo_estacion",
    "normalize_direccion",
    "capitalize_provincia",
    "is_valid_email",
    "separate_email_and_url",
    "parse_coordinates",
    "parse_single_coordinate",
    "find_column",
    "safe_get",
    "make_code",
    "DIAS_MAPPING",
    # Spanish locations
    "PROVINCIAS_VALIDAS",
    "PROVINCIA_ALIASES",
    "RANGOS_CODIGOS_POSTALES",
    "RANGOS_COORDENADAS_PROVINCIAS",
    "RANGO_COORDENADAS_ESPANA",
    "normalizar_provincia",
    "obtener_provincia_por_codigo_postal",
    "validar_codigo_postal",
    "obtener_rango_coordenadas_provincia",
    # Validators
    "validar_provincia",
    "normalizar_municipio",
    "validar_ubicacion_por_codigo_postal",
    "validar_coordenadas",
    "validar_campos_obligatorios",
    "validar_estacion_completa",
    "log_estadisticas_validacion",
    # Duplicate detector
    "DetectorDuplicados",
    "DuplicateFilter",
    "detectar_duplicados",
    "CriterioDuplicado",
    "CriterioNombreCodigoPostal",
    "CriterioNombreDireccion",
    "CriterioCoordenadas",
    "calcular_distancia_haversine",
    "normalizar_para_comparacion",
    "extraer_nombre_base",
]
