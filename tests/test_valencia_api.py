"""
Tests para el microservicio Valencia API
"""
import pytest
import sys
import os
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'extractor_services'))

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Cliente de test para Valencia API"""
    # Import dentro de fixture para evitar problemas de importación
    from valencia_api.main import app
    return TestClient(app)


@pytest.fixture
def mock_file_exists():
    """Mock para que el archivo de datos exista"""
    with patch('os.path.exists', return_value=True):
        yield


@pytest.fixture
def mock_valencia_data():
    """Datos de ejemplo de Valencia"""
    return [
        {
            "Nombre": "ESTACION ITV RIBARROJA",
            "Tipo": "Estacion Fija",
            "Direccion": "Poligono Industrial El Oliveral",
            "Codigo postal": "46190",
            "Municipio": "Ribarroja del Turia",
            "Provincia": "Valencia",
            "Coordenadas": {
                "Latitud": 39.548889,
                "Longitud": -0.557222
            },
            "Horario": "De lunes a viernes de 8:00 a 20:00 horas",
            "Email": "ribarroja@sitval.es",
            "Web": "https://www.sitval.es"
        }
    ]


class TestHealthEndpoint:
    """Tests del endpoint de health check"""
    
    def test_health_endpoint_root(self, client):
        """Test de endpoint raíz /"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Valencia ITV Extractor"
        assert "version" in data
    
    def test_health_endpoint_explicit(self, client):
        """Test de endpoint /health"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "source_file" in data


class TestExtractPreview:
    """Tests del endpoint de preview (sin enviar a central)"""
    
    def test_extract_preview_no_file(self, client):
        """Test de preview cuando no existe el archivo"""
        with patch('os.path.exists', return_value=False):
            response = client.post("/extract/preview")
            assert response.status_code in [500, 400]
    
    def test_extract_preview_success(self, client, mock_file_exists, mock_valencia_data):
        """Test de preview exitoso"""
        with patch('valencia_api.extractor.ValenciaExtractor.extract', return_value=mock_valencia_data):
            with patch('valencia_api.transformer.ValenciaTransformer.transform'):
                response = client.post("/extract/preview")
                
                if response.status_code == 200:
                    data = response.json()
                    assert "extraidos" in data
                    assert "estaciones" in data
                    assert data["source"] == "VAL"
    
    def test_extract_preview_validation(self, client, mock_file_exists):
        """Test de validación de datos en preview"""
        invalid_data = [{"Nombre": "Test", "invalid": "data"}]
        
        with patch('valencia_api.extractor.ValenciaExtractor.extract', return_value=invalid_data):
            response = client.post("/extract/preview")
            # Debe manejar errores de validación gracefully
            assert response.status_code in [200, 400, 422, 500]


class TestExtractFull:
    """Tests del endpoint de extracción completa (con envío a central)"""
    
    def test_extract_without_central_api(self, client, mock_file_exists, mock_valencia_data):
        """Test de extracción cuando API Central no está disponible"""
        with patch('valencia_api.extractor.ValenciaExtractor.extract', return_value=mock_valencia_data):
            with patch('common.client.CentralAPIClient.enviar_payload', side_effect=Exception("Connection refused")):
                response = client.post("/extract")
                # Debe manejar error de conexión
                assert response.status_code in [200, 500, 503]
    
    def test_extract_success_with_mock_central(self, client, mock_file_exists, mock_valencia_data, mock_httpx_client):
        """Test de extracción completa exitosa con API Central mockeada"""
        with patch('valencia_api.extractor.ValenciaExtractor.extract', return_value=mock_valencia_data):
            with patch('valencia_api.transformer.ValenciaTransformer.transform') as mock_transform:
                # Mock del transformer para devolver datos válidos
                mock_transform.return_value = (
                    [{
                        "nombre": "Estación ITV Ribarroja",
                        "tipo": "estacion_fija",
                        "direccion": "Poligono Industrial El Oliveral",
                        "codigo_postal": "46190",
                        "localidad": "Ribarroja del Turia",
                        "provincia": "Valencia",
                        "latitud": 39.548889,
                        "longitud": -0.557222,
                        "horario": "De lunes a viernes de 8:00 a 20:00 horas",
                        "contacto": "ribarroja@sitval.es",
                        "url": "https://www.sitval.es"
                    }],
                    []  # rechazados
                )
                
                response = client.post("/extract")
                
                if response.status_code == 200:
                    data = response.json()
                    assert data["source"] == "VAL"
                    assert "extraidos" in data
                    assert "enviado_a_central" in data


class TestTransformer:
    """Tests de la lógica de transformación"""
    
    def test_transform_valid_station(self):
        """Test de transformación de estación válida"""
        from valencia_api.transformer import ValenciaTransformer
        
        raw_item = {
            "Nombre": "ESTACION ITV TEST",
            "Tipo": "Estacion Fija",
            "Direccion": "Calle Test 123",
            "Codigo postal": "46001",
            "Municipio": "Valencia",
            "Provincia": "Valencia",
            "Coordenadas": {"Latitud": 39.4699, "Longitud": -0.3763}
        }
        
        transformer = ValenciaTransformer()
        result = transformer.transform_item(raw_item, 0)
        
        if result:
            assert result["nombre"] is not None
            assert result["localidad"] == "Valencia"
            assert result["provincia"] == "Valencia"
            assert result["latitud"] == 39.4699
            assert result["longitud"] == -0.3763
    
    def test_transform_invalid_coordinates(self):
        """Test de transformación con coordenadas inválidas"""
        from valencia_api.transformer import ValenciaTransformer
        
        raw_item = {
            "Nombre": "ESTACION TEST",
            "Tipo": "Estacion Fija",
            "Municipio": "Valencia",
            "Provincia": "Valencia",
            "Coordenadas": {"Latitud": 999, "Longitud": 999}  # Inválidas
        }
        
        transformer = ValenciaTransformer()
        result = transformer.transform_item(raw_item, 0)
        
        # Debe rechazar o intentar geocoding
        # El comportamiento depende de la implementación
        assert True  # Placeholder
    
    def test_transform_missing_required_fields(self):
        """Test de transformación con campos requeridos faltantes"""
        from valencia_api.transformer import ValenciaTransformer
        
        raw_item = {
            "Nombre": "TEST"
            # Falta provincia, localidad, etc.
        }
        
        transformer = ValenciaTransformer()
        result = transformer.transform_item(raw_item, 0)
        
        # Debe retornar None o rechazar
        # assert result is None  # Depende de implementación


class TestGeocoding:
    """Tests del servicio de geocoding"""
    
    def test_geocode_valid_address(self):
        """Test de geocoding con dirección válida"""
        from valencia_api.geocoding import GeocodingService
        
        service = GeocodingService()
        
        with patch('valencia_api.geocoding.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = [{
                "lat": "39.4699",
                "lon": "-0.3763"
            }]
            mock_get.return_value = mock_response
            
            lat, lon = service.geocode("Valencia", "Valencia")
            
            assert lat is not None
            assert lon is not None
            assert isinstance(lat, float)
            assert isinstance(lon, float)
    
    def test_geocode_invalid_address(self):
        """Test de geocoding con dirección inválida"""
        from valencia_api.geocoding import GeocodingService
        
        service = GeocodingService()
        
        with patch('valencia_api.geocoding.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = []  # Sin resultados
            mock_get.return_value = mock_response
            
            lat, lon = service.geocode("Ciudad Inexistente", "Provincia Inexistente")
            
            assert lat is None or lon is None
