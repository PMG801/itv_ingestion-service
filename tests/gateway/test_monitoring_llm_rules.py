"""Tests para el endpoint de invalidación de reglas LLM."""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from apps.gateway.main import app


@pytest.mark.asyncio
async def test_invalidate_llm_rule_endpoint_exists() -> None:
    """Test que el endpoint DELETE existe y responde."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Mock la función de queries para evitar conexión a BD
        with patch(
            "apps.gateway.routers.monitoring.deactivate_llm_mapping_rule_by_key",
            new_callable=AsyncMock,
            return_value=0,
        ):
            response = await client.delete(
                "/api/v1/monitoring/llm-rules/test_source/TestProvince"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "not_found"
            assert data["deactivated_count"] == 0


@pytest.mark.asyncio
async def test_invalidate_llm_rule_success() -> None:
    """Test que el endpoint devuelve success cuando se deactiva una regla."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Mock la función para simular que deactivó 1 regla
        with patch(
            "apps.gateway.routers.monitoring.deactivate_llm_mapping_rule_by_key",
            new_callable=AsyncMock,
            return_value=1,
        ):
            response = await client.delete(
                "/api/v1/monitoring/llm-rules/test_source/TestProvince"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["deactivated_count"] == 1


@pytest.mark.asyncio
async def test_invalidate_llm_rule_invalid_params() -> None:
    """Test que el endpoint valida parámetros."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # FastAPI devuelve 404 cuando la ruta no coincide
        response = await client.delete("/api/v1/monitoring/llm-rules/")
        assert response.status_code in (404, 307)  # Not found or redirect
