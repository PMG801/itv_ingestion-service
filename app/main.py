"""  
Punto de entrada principal de la aplicación FastAPI.

Este módulo configura e inicializa la aplicación FastAPI que sirve como API central
para el sistema de búsqueda y gestión de estaciones ITV.

Componentes principales:
- Configuración de FastAPI con lifespan para gestión de recursos
- Middleware CORS para permitir peticiones desde el frontend
- Routers para búsqueda y carga de datos
- Conexión a base de datos PostgreSQL
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.db.connection import DatabaseConnection
# Importar routers desde sus nuevas ubicaciones
from app.carga.routers import load_router, ingest_router
from app.busqueda.routers import stations_router, geo_router

# Configuración del sistema de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestor de ciclo de vida de la aplicación.
    
    Este context manager se ejecuta al iniciar y cerrar la aplicación:
    - Al inicio: establece la conexión con la base de datos PostgreSQL
    - Al cerrar: cierra la conexión de forma ordenada
    
    Args:
        app: Instancia de la aplicación FastAPI
        
    Yields:
        Control a la aplicación mientras está en ejecución
        
    Raises:
        Exception: Si hay errores al conectar con la base de datos
    """
    logger.info("Iniciando aplicación...")
    try:
        # Establecer conexión con PostgreSQL usando la URL de configuración
        DatabaseConnection.connect_to_database(settings.database_url)
        logger.info("Aplicación iniciada correctamente")
        yield  # Aplicación en ejecución
    except Exception as e:
        logger.error(f"Error al iniciar: {e}")
        raise e
    finally:
        # Limpieza: cerrar pool de conexiones
        logger.info("Cerrando aplicación...")
        DatabaseConnection.close_database_connection()
        logger.info("Aplicación cerrada correctamente")


# Crear instancia de aplicación FastAPI
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan  # Gestor de ciclo de vida para recursos
)

# --- CONFIGURACIÓN DE CORS ---
# Middleware para permitir peticiones cross-origin desde el frontend
# IMPORTANTE: En producción, especificar orígenes específicos en lugar de "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes (solo para desarrollo)
    allow_credentials=True,  # Permite envío de cookies/auth headers
    allow_methods=["*"],  # Permite todos los métodos HTTP (GET, POST, DELETE, etc)
    allow_headers=["*"],  # Permite todos los headers
)

# --- REGISTRO DE ROUTERS ---
# Cada router maneja un conjunto específico de endpoints relacionados

# Router de carga: endpoints para iniciar/consultar procesos de carga de datos
app.include_router(load_router.router)

# Router de búsqueda: endpoints para buscar estaciones ITV
app.include_router(stations_router.router)

# Router de geografía: endpoints para obtener provincias y datos geográficos
app.include_router(geo_router.router)

# Router de ingesta: endpoint para recibir datos de microservicios extractores
app.include_router(ingest_router.router)

@app.get("/")
async def root():
    """
    Endpoint raíz de la API.
    
    Retorna información básica sobre la API y enlace a la documentación.
    
    Returns:
        dict: Información de la API (mensaje, versión, enlace a docs)
    """
    return {
        "message": "IEI API",
        "version": settings.api_version,
        "docs": "/docs"
    }