"""
API de Búsqueda - Microservicio para búsqueda de estaciones ITV
Puerto: 8004

Endpoints:
- /api/estaciones/ - Buscar estaciones con filtros
- /api/provincias/ - Listar provincias disponibles
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.db.connection import DatabaseConnection
from app.busqueda.routers import stations_router, geo_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    logger.info("Iniciando API de Búsqueda...")
    try:
        DatabaseConnection.connect_to_database(settings.database_url)
        logger.info("API de Búsqueda iniciada correctamente")
        yield
    except Exception as e:
        logger.error(f"Error al iniciar API de Búsqueda: {e}")
        raise e
    finally:
        logger.info("Cerrando API de Búsqueda...")
        DatabaseConnection.close_database_connection()
        logger.info("API de Búsqueda cerrada correctamente")


app = FastAPI(
    title="ITV Buscador - API de Búsqueda",
    version=settings.api_version,
    description="Microservicio para búsqueda de estaciones ITV con filtros geográficos",
    lifespan=lifespan
)

# --- CORS MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROUTERS ---
app.include_router(stations_router.router)
app.include_router(geo_router.router)


@app.get("/")
async def root():
    return {
        "service": "API de Búsqueda",
        "version": settings.api_version,
        "docs": "/docs",
        "endpoints": {
            "estaciones": "/api/estaciones/",
            "provincias": "/api/provincias/"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "busqueda"}
