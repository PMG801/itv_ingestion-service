"""
API Extractora de Valencia
Microservicio para extracción y transformación de datos de ITVs de la Comunidad Valenciana
"""
import sys
import os

# Añadir el directorio raíz al path para importar módulos comunes
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from common import (
    ValenciaSettings,
    PayloadExtraccion,
    EstadisticasExtraccion,
    ExtractorHealthResponse,
    ExtractorPreviewResponse,
    ExtractorResponse,
    create_client
)
from extractor import ValenciaExtractorService

# Configuración
settings = ValenciaSettings()

# Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Servicio de extracción
extractor_service = ValenciaExtractorService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    logger.info(f"🚀 Iniciando {settings.service_name} v{settings.service_version}")
    logger.info(f"📁 Archivo fuente: {settings.source_file}")
    logger.info(f"🌐 API Central: {settings.central_api_url}")
    yield
    logger.info(f"👋 Cerrando {settings.service_name}")


app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    description="Microservicio para extracción de datos de ITVs de la Comunidad Valenciana",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=ExtractorHealthResponse)
async def health():
    """Estado del servicio"""
    return ExtractorHealthResponse(
        service=settings.service_name,
        status="healthy",
        version=settings.service_version,
        source_file=settings.source_file
    )


@app.get("/health", response_model=ExtractorHealthResponse)
async def health_check():
    """Endpoint de health check"""
    return await health()


@app.post("/extract/preview", response_model=ExtractorPreviewResponse)
async def preview_extraction():
    """
    Ejecuta la extracción y transformación SIN enviar a la API central.
    Útil para testing y verificación de datos.
    """
    logger.info("🔍 Iniciando preview de extracción...")
    
    try:
        payload = extractor_service.extract_and_transform(settings.source_file)
        
        return ExtractorPreviewResponse(
            status="success",
            source=settings.source_id,
            payload=payload,
            mensaje=f"Preview completado: {len(payload.estaciones)} estaciones extraídas, {len(payload.rechazados)} rechazadas"
        )
    except FileNotFoundError as e:
        logger.error(f"❌ Archivo no encontrado: {e}")
        raise HTTPException(status_code=404, detail=f"Archivo fuente no encontrado: {settings.source_file}")
    except Exception as e:
        logger.error(f"❌ Error en preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract", response_model=ExtractorResponse)
async def execute_extraction():
    """
    Ejecuta la extracción completa:
    1. Lee el archivo fuente
    2. Transforma los datos
    3. Envía el JSON a la API central
    """
    logger.info("🚀 Iniciando extracción completa...")
    
    try:
        # 1. Extraer y transformar
        payload = extractor_service.extract_and_transform(settings.source_file)
        
        logger.info(f"✅ Extracción completada: {len(payload.estaciones)} estaciones")
        
        # 2. Enviar a API central
        client = create_client(settings.central_api_url, settings.central_api_timeout)
        
        # Enviar payload directamente
        try:
            respuesta = await client.enviar_payload(payload)
        except Exception as e:
            logger.warning(f"⚠️ No se pudo enviar a API central: {e}")
            return ExtractorResponse(
                status="pending",
                source=settings.source_id,
                extraidos=len(payload.estaciones),
                enviado_a_central=False,
                error=f"Error al enviar a API central: {str(e)}"
            )
        
        return ExtractorResponse(
            status="success",
            source=settings.source_id,
            extraidos=len(payload.estaciones),
            enviado_a_central=True,
            respuesta_central=respuesta
        )
        
    except FileNotFoundError as e:
        logger.error(f"❌ Archivo no encontrado: {e}")
        raise HTTPException(status_code=404, detail=f"Archivo fuente no encontrado: {settings.source_file}")
    except Exception as e:
        logger.error(f"❌ Error en extracción: {e}")
        return ExtractorResponse(
            status="error",
            source=settings.source_id,
            extraidos=0,
            enviado_a_central=False,
            error=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
