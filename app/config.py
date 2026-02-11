"""  
Configuración global de la aplicación.

Este módulo maneja todas las variables de configuración de la aplicación,
cargándolas desde variables de entorno o archivo .env.

Uso de Pydantic Settings:
- Validación automática de tipos
- Valores por defecto
- Carga desde archivo .env
- Manejo seguro de secretos (database_url)

Variables requeridas en .env:
- DATABASE_URL: URL de conexión a PostgreSQL (ej: postgresql://user:pass@host:5432/db)
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Clase de configuración usando Pydantic Settings.
    
    Los valores se cargan automáticamente desde:
    1. Variables de entorno del sistema
    2. Archivo .env en la raíz del proyecto
    
    Attributes:
        database_url: URL de conexión a PostgreSQL (obligatorio)
        api_title: Título de la API mostrado en la documentación
        api_version: Versión de la API
        api_description: Descripción de la API
        external_api_timeout: Timeout para llamadas a APIs externas (segundos)
        max_retries: Número máximo de reintentos para operaciones fallidas
        max_image_size_mb: Tamaño máximo de imágenes permitido (MB)
    """
    
    # === CONFIGURACIÓN DE BASE DE DATOS ===
    database_url: str  # Obligatorio - debe estar en .env
    
    # === INFORMACIÓN DE LA API ===
    api_title: str = "IEI API"
    api_version: str = "1.0.0"
    api_description: str = "API para gestión y búsqueda de estaciones ITV"  
    
    # === CONFIGURACIÓN GENERAL ===
    external_api_timeout: int = 30  # Timeout para APIs externas
    max_retries: int = 3  # Reintentos para operaciones
    max_image_size_mb: int = 5  # Límite de tamaño de imágenes
    
    class Config:
        """Configuración de Pydantic Settings"""
        env_file = ".env"  # Archivo de donde leer variables
        case_sensitive = False  # No distinguir mayúsculas/minúsculas
        extra = "ignore"  # Ignorar variables extra no definidas


# Instancia global de configuración - usar en toda la aplicación
settings = Settings()