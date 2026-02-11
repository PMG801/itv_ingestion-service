"""
Gateway Service - FastAPI Application
Entry point for the API Gateway.
"""
from fastapi import FastAPI

app = FastAPI(
    title="ITV Ingestion Gateway",
    description="API Gateway for ITV station data ingestion",
    version="0.1.0"
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gateway"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "ITV Ingestion Gateway",
        "version": "0.1.0",
        "status": "running"
    }
