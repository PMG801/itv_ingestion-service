"""
Configuración compartida de pytest para todos los tests.
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch

# Añadir paths necesarios para imports
project_root = os.path.dirname(os.path.dirname(__file__))
extractor_services = os.path.join(project_root, 'extractor_services')

sys.path.insert(0, project_root)
sys.path.insert(0, extractor_services)
sys.path.insert(0, os.path.join(extractor_services, 'valencia_api'))
sys.path.insert(0, os.path.join(extractor_services, 'catalunya_api'))
sys.path.insert(0, os.path.join(extractor_services, 'galicia_api'))


@pytest.fixture
def mock_database_url(monkeypatch):
    """Mock de DATABASE_URL para tests sin BD real"""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/testdb")


@pytest.fixture
def sample_estacion():
    """Estación de ejemplo válida"""
    return {
        "nombre": "Estación ITV de Valencia Test",
        "tipo": "estacion_fija",
        "direccion": "Calle Test 123",
        "codigo_postal": "46001",
        "localidad": "Valencia",
        "provincia": "Valencia",
        "latitud": 39.4699,
        "longitud": -0.3763,
        "horario": "L-V 8:00-20:00",
        "contacto": "test@itv.es",
        "url": "https://test.com"
    }


@pytest.fixture
def sample_payload():
    """Payload de extracción completo"""
    from datetime import datetime
    return {
        "source": "VAL",
        "timestamp": datetime.now().isoformat(),
        "estaciones": [
            {
                "nombre": "Estación Test 1",
                "tipo": "estacion_fija",
                "direccion": "Calle Test 1",
                "codigo_postal": "46001",
                "localidad": "Valencia",
                "provincia": "Valencia",
                "latitud": 39.4699,
                "longitud": -0.3763
            },
            {
                "nombre": "Estación Test 2",
                "tipo": "estacion_movil",
                "direccion": "Calle Test 2",
                "codigo_postal": "08001",
                "localidad": "Barcelona",
                "provincia": "Barcelona",
                "latitud": 41.3851,
                "longitud": 2.1734
            }
        ],
        "rechazados": [],
        "stats": {
            "total_raw": 2,
            "transformados": 2,
            "rechazados": 0
        }
    }


@pytest.fixture
def mock_central_api_success():
    """Mock de respuesta exitosa de API Central"""
    return {
        "status": "success",
        "source": "VAL",
        "recibidos": 2,
        "insertados": 2,
        "duplicados_detectados": 0,
        "errores_insercion": 0,
        "mensaje": "Carga completada"
    }


@pytest.fixture
def mock_httpx_client(mock_central_api_success):
    """Mock del cliente httpx para llamadas a API Central"""
    with patch('common.client.httpx.AsyncClient') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_central_api_success
        
        mock_instance = Mock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post.return_value = mock_response
        
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def skip_if_services_not_running():
    """Skip test si los servicios de Docker no están corriendo"""
    import socket
    try:
        with socket.create_connection(('localhost', 8000), timeout=1):
            return True
    except:
        pytest.skip("Servicios no están corriendo (docker-compose down?)")
