"""
ITV Ingestion Gateway - FastAPI Application.

Main entry point for the gateway service that receives external data via HTTP
and publishes it to RabbitMQ for asynchronous processing.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.messaging import RabbitMQClient
from core.database import dispose_engine

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager for startup and shutdown events.

    Handles initialization of RabbitMQ connection and database engine
    on startup, and graceful cleanup on shutdown.

    Args:
        app: FastAPI application instance.

    Yields:
        None: Control to the application during its runtime.
    """
    # Startup: Initialize connections
    logger.info(f"Starting {settings.APP_NAME}...")

    try:
        # Initialize RabbitMQ client
        rabbitmq_client = RabbitMQClient()
        await rabbitmq_client.connect()
        app.state.rabbitmq = rabbitmq_client
        logger.info("RabbitMQ client initialized and connected")

        # Store settings in app state for easy access
        app.state.settings = settings

        logger.info(f"{settings.APP_NAME} started successfully")

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        raise

    yield  # Application runs here

    # Shutdown: Cleanup connections
    logger.info(f"Shutting down {settings.APP_NAME}...")

    try:
        # Disconnect RabbitMQ
        if hasattr(app.state, "rabbitmq"):
            await app.state.rabbitmq.disconnect()
            logger.info("RabbitMQ client disconnected")

        # Dispose database engine
        await dispose_engine()
        logger.info("Database engine disposed")

        logger.info(f"{settings.APP_NAME} shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


# Create FastAPI application with lifespan
app = FastAPI(
    title="ITV Ingestion Gateway",
    description="API Gateway for ITV station data ingestion from external sources",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for container orchestration.

    Returns:
        dict: Service health status and RabbitMQ connection state.
    """
    rabbitmq_connected = hasattr(app.state, "rabbitmq") and app.state.rabbitmq.is_connected

    return {
        "status": "healthy" if rabbitmq_connected else "degraded",
        "service": "gateway",
        "version": "0.1.0",
        "rabbitmq_connected": rabbitmq_connected,
    }


@app.get("/")
async def root():
    """
    Root endpoint with service information.

    Returns:
        dict: Service metadata and status.
    """
    return {
        "service": "ITV Ingestion Gateway",
        "version": "0.1.0",
        "status": "running",
        "description": "Gateway for ingesting ITV station data from Catalunya, Valencia, and Galicia",
    }


# Import and include routers
from apps.gateway.routers import ingest, monitoring, upload, stations

# New ingest API (v1)
app.include_router(ingest.router, prefix="/api/v1", tags=["ingestion"])

# Monitoring API for dashboards
app.include_router(monitoring.router, tags=["monitoring"])

# Upload & injection API
app.include_router(upload.router, tags=["injection"])

# Stations read API for frontend search/map
app.include_router(stations.router, tags=["stations"])
