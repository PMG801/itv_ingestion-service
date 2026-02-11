"""
Configuración común para todos los servicios extractores.
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class ExtractorSettings(BaseSettings):
    """Configuración base para los servicios extractores"""
    
    # API Central
    central_api_url: str = os.getenv("CENTRAL_API_URL", "http://127.0.0.1:8000")
    central_api_timeout: int = int(os.getenv("CENTRAL_API_TIMEOUT", "60"))
    
    # Configuración del servicio
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        extra = "allow"


class ValenciaSettings(ExtractorSettings):
    """Configuración específica para el extractor de Valencia"""
    service_name: str = "Valencia Extractor"
    service_version: str = "1.0.0"
    source_id: str = "VAL"
    source_file: str = os.getenv("SOURCE_FILE", "../data/estaciones_cv.json")
    port: int = int(os.getenv("PORT", "8001"))


class CatalunyaSettings(ExtractorSettings):
    """Configuración específica para el extractor de Catalunya"""
    service_name: str = "Catalunya Extractor"
    service_version: str = "1.0.0"
    source_id: str = "CAT"
    source_file: str = os.getenv("SOURCE_FILE", "../data/estaciones_cat.xml")
    port: int = int(os.getenv("PORT", "8002"))


class GaliciaSettings(ExtractorSettings):
    """Configuración específica para el extractor de Galicia"""
    service_name: str = "Galicia Extractor"
    service_version: str = "1.0.0"
    source_id: str = "GAL"
    source_file: str = os.getenv("SOURCE_FILE", "../data/estaciones_gal.csv")
    port: int = int(os.getenv("PORT", "8003"))
