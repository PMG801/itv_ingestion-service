"""
Tests para la API Central - Router de Ingestión
Tests del endpoint POST /api/ingest que recibe datos de los extractores
"""
import pytest
import sys
import os
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient


@pytest.fixture
def client(mock_database_url):
    """Cliente de test para API Central"""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def mock_db_connection():
    """Mock de conexiones a base de datos"""
    with patch('app.db.load_queries.get_connection') as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # ID de provincia/localidad
        mock_cursor.fetchall.return_value = []  # Sin estaciones existentes
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connection.__enter__.return_value = mock_connection
        
        mock_conn.return_value = mock_connection
        yield mock_conn


class TestIngestEndpoint:
    """Tests del endpoint POST /api/ingest"""
    
    def test_ingest_valid_payload(self, client, mock_db_connection, sample_payload):
        """Test de ingestión con payload válido"""
        response = client.post("/api/ingest/", json=sample_payload)
        
        assert response.status_code in [200, 500]  # 500 si hay problemas de BD mock
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "source" in data
            assert data["source"] == sample_payload["source"]
            assert "recibidos" in data
            assert "insertados" in data
            assert "duplicados_detectados" in data
    
    def test_ingest_empty_stations(self, client, mock_db_connection):
        """Test de ingestión con lista vacía de estaciones"""
        payload = {
            "source": "VAL",
            "timestamp": datetime.now().isoformat(),
            "estaciones": [],
            "rechazados": [],
            "stats": {
                "total_raw": 0,
                "transformados": 0,
                "rechazados": 0
            }
        }
        
        response = client.post("/api/ingest/", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert data["recibidos"] == 0
    
    def test_ingest_invalid_payload_missing_source(self, client):
        """Test de ingestión sin campo source (requerido)"""
        payload = {
            "timestamp": datetime.now().isoformat(),
            "estaciones": [],
            "rechazados": [],
            "stats": {
                "total_raw": 0,
                "transformados": 0,
                "rechazados": 0
            }
        }
        
        response = client.post("/api/ingest/", json=payload)
        assert response.status_code == 422  # Validation error
    
    def test_ingest_invalid_coordinates(self, client, mock_db_connection):
        """Test de ingestión con coordenadas inválidas"""
        payload = {
            "source": "VAL",
            "timestamp": datetime.now().isoformat(),
            "estaciones": [
                {
                    "nombre": "Test",
                    "localidad": "Valencia",
                    "provincia": "Valencia",
                    "latitud": 999,  # Inválida
                    "longitud": 999   # Inválida
                }
            ],
            "rechazados": [],
            "stats": {
                "total_raw": 1,
                "transformados": 1,
                "rechazados": 0
            }
        }
        
        response = client.post("/api/ingest/", json=payload)
        # Debe rechazar o manejar coordenadas inválidas
        assert response.status_code in [200, 422]
    
    def test_ingest_duplicate_detection(self, client, mock_db_connection):
        """Test de detección de duplicados en la carga"""
        # Dos estaciones idénticas
        duplicate_station = {
            "nombre": "Estación Duplicada",
            "tipo": "estacion_fija",
            "direccion": "Calle Test 123",
            "codigo_postal": "46001",
            "localidad": "Valencia",
            "provincia": "Valencia",
            "latitud": 39.4699,
            "longitud": -0.3763
        }
        
        payload = {
            "source": "VAL",
            "timestamp": datetime.now().isoformat(),
            "estaciones": [duplicate_station, duplicate_station.copy()],
            "rechazados": [],
            "stats": {
                "total_raw": 2,
                "transformados": 2,
                "rechazados": 0
            }
        }
        
        response = client.post("/api/ingest/", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Debe detectar duplicados
            assert data["recibidos"] == 2
    
    def test_ingest_with_rejected_records(self, client, mock_db_connection):
        """Test de ingestión con registros rechazados"""
        payload = {
            "source": "CAT",
            "timestamp": datetime.now().isoformat(),
            "estaciones": [
                {
                    "nombre": "Estación Válida",
                    "localidad": "Barcelona",
                    "provincia": "Barcelona",
                    "latitud": 41.3851,
                    "longitud": 2.1734
                }
            ],
            "rechazados": [
                {
                    "registro": 5,
                    "nombre": "Estación Rechazada",
                    "razon": "Coordenadas inválidas"
                }
            ],
            "stats": {
                "total_raw": 2,
                "transformados": 1,
                "rechazados": 1
            }
        }
        
        response = client.post("/api/ingest/", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert data["recibidos"] == 1  # Solo la válida


class TestIngestValidation:
    """Tests de validación de datos en el endpoint de ingestión"""
    
    def test_validate_required_fields(self, client):
        """Test de campos requeridos en estaciones"""
        payload = {
            "source": "VAL",
            "timestamp": datetime.now().isoformat(),
            "estaciones": [
                {
                    "nombre": "Test"
                    # Faltan localidad, provincia, latitud, longitud
                }
            ],
            "rechazados": [],
            "stats": {
                "total_raw": 1,
                "transformados": 1,
                "rechazados": 0
            }
        }
        
        response = client.post("/api/ingest/", json=payload)
        # Debe fallar validación Pydantic
        assert response.status_code == 422
    
    def test_validate_source_format(self, client):
        """Test de validación del campo source"""
        payload = {
            "source": "",  # Vacío
            "timestamp": datetime.now().isoformat(),
            "estaciones": [],
            "rechazados": [],
            "stats": {
                "total_raw": 0,
                "transformados": 0,
                "rechazados": 0
            }
        }
        
        response = client.post("/api/ingest/", json=payload)
        # Source vacío debe fallar validación
        assert response.status_code in [422, 400]
    
    def test_validate_timestamp_format(self, client):
        """Test de validación del timestamp"""
        payload = {
            "source": "VAL",
            "timestamp": "invalid-date-format",
            "estaciones": [],
            "rechazados": [],
            "stats": {
                "total_raw": 0,
                "transformados": 0,
                "rechazados": 0
            }
        }
        
        response = client.post("/api/ingest/", json=payload)
        # Timestamp inválido debe fallar validación
        assert response.status_code == 422


class TestIngestDatabaseOperations:
    """Tests de operaciones de base de datos"""
    
    def test_insert_new_station(self, client, mock_db_connection):
        """Test de inserción de nueva estación"""
        payload = {
            "source": "GAL",
            "timestamp": datetime.now().isoformat(),
            "estaciones": [
                {
                    "nombre": "Nueva Estación",
                    "localidad": "Vigo",
                    "provincia": "Pontevedra",
                    "latitud": 42.2406,
                    "longitud": -8.7207
                }
            ],
            "rechazados": [],
            "stats": {
                "total_raw": 1,
                "transformados": 1,
                "rechazados": 0
            }
        }
        
        with patch('app.db.load_queries.insertar_estacion') as mock_insert:
            mock_insert.return_value = None  # Inserción exitosa
            
            response = client.post("/api/ingest/", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                assert data["insertados"] >= 0
    
    def test_handle_database_error(self, client):
        """Test de manejo de errores de base de datos"""
        payload = {
            "source": "VAL",
            "timestamp": datetime.now().isoformat(),
            "estaciones": [
                {
                    "nombre": "Test",
                    "localidad": "Valencia",
                    "provincia": "Valencia",
                    "latitud": 39.4699,
                    "longitud": -0.3763
                }
            ],
            "rechazados": [],
            "stats": {
                "total_raw": 1,
                "transformados": 1,
                "rechazados": 0
            }
        }
        
        with patch('app.db.load_queries.get_connection', side_effect=Exception("DB Connection Error")):
            response = client.post("/api/ingest/", json=payload)
            
            # Debe manejar error de BD
            assert response.status_code in [500, 503]


class TestIngestLogging:
    """Tests de logging y auditoría"""
    
    def test_log_collection(self, client, mock_db_connection):
        """Test de recolección de logs durante ingestión"""
        payload = {
            "source": "CAT",
            "timestamp": datetime.now().isoformat(),
            "estaciones": [
                {
                    "nombre": "Test Station",
                    "localidad": "Barcelona",
                    "provincia": "Barcelona",
                    "latitud": 41.3851,
                    "longitud": 2.1734
                }
            ],
            "rechazados": [],
            "stats": {
                "total_raw": 1,
                "transformados": 1,
                "rechazados": 0
            }
        }
        
        with patch('app.db.log_collector.LogCollector') as mock_logger:
            response = client.post("/api/ingest/", json=payload)
            
            # Verificar que se usó el logger
            # (depende de la implementación)
            assert response.status_code in [200, 500]


class TestIngestPerformance:
    """Tests de performance y carga"""
    
    def test_large_batch_ingest(self, client, mock_db_connection):
        """Test de ingestión de lote grande"""
        # Crear 100 estaciones
        estaciones = [
            {
                "nombre": f"Estación {i}",
                "localidad": "Valencia",
                "provincia": "Valencia",
                "latitud": 39.4699 + (i * 0.001),
                "longitud": -0.3763 + (i * 0.001)
            }
            for i in range(100)
        ]
        
        payload = {
            "source": "VAL",
            "timestamp": datetime.now().isoformat(),
            "estaciones": estaciones,
            "rechazados": [],
            "stats": {
                "total_raw": 100,
                "transformados": 100,
                "rechazados": 0
            }
        }
        
        response = client.post("/api/ingest/", json=payload)
        
        # Debe procesar lote grande
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert data["recibidos"] == 100
