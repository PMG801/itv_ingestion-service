"""
API de Carga - Microservicio para carga de datos ITV
Puerto: 8000

Endpoints:
- /api/carga/ - Iniciar carga de datos
- /api/carga/resultado/{fuente} - Consultar resultado de carga
- /api/carga/limpiar-todo - Limpiar base de datos
- /api/ingest/ - Recibir datos de extractores
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.db.connection import DatabaseConnection
from app.carga.routers import load_router, ingest_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    logger.info("Iniciando API de Carga...")
    try:
        DatabaseConnection.connect_to_database(settings.database_url)
        logger.info("API de Carga iniciada correctamente")
        yield
    except Exception as e:
        logger.error(f"Error al iniciar API de Carga: {e}")
        raise e
    finally:
        logger.info("Cerrando API de Carga...")
        DatabaseConnection.close_database_connection()
        logger.info("API de Carga cerrada correctamente")


app = FastAPI(
    title="ITV Buscador - API de Carga",
    version=settings.api_version,
    description="Microservicio para carga de datos de estaciones ITV desde múltiples fuentes",
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
app.include_router(load_router.router)
app.include_router(ingest_router.router)


@app.get("/")
async def root():
    return {
        "service": "API de Carga",
        "version": settings.api_version,
        "docs": "/docs",
        "endpoints": {
            "carga": "/api/carga/",
            "ingest": "/api/ingest/"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "carga"}
