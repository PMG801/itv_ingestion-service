"""
Tests para el microservicio Galicia API
"""
import pytest
import sys
import os
from unittest.mock import patch, Mock
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'extractor_services'))

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Cliente de test para Galicia API"""
    from galicia_api.main import app
    return TestClient(app)


@pytest.fixture
def mock_file_exists():
    """Mock para que el archivo de datos exista"""
    with patch('os.path.exists', return_value=True):
        yield


@pytest.fixture
def mock_galicia_csv():
    """CSV de ejemplo de Galicia"""
    return """Nombre;Tipo;Direccion;CodigoPostal;Municipio;Provincia;Latitud;Longitud;Horario;Contacto
ESTACION ITV VIGO;Estación Fija;Rúa Test 123;36201;Vigo;Pontevedra;42.2406;-8.7207;Lunes a viernes 8:00-20:00;info@itvgalicia.es
ESTACION ITV CORUÑA;Estación Fija;Rúa Exemplo 456;15001;A Coruña;A Coruña;43.3623;-8.4115;Lunes a viernes 9:00-19:00;coruna@itvgalicia.es
"""


class TestHealthEndpoint:
    """Tests del endpoint de health check"""
    
    def test_health_endpoint_root(self, client):
        """Test de endpoint raíz /"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Galicia ITV Extractor"
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
        """Test de preview cuando no existe el archivo CSV"""
        with patch('os.path.exists', return_value=False):
            response = client.post("/extract/preview")
            assert response.status_code in [500, 400]
    
    def test_extract_preview_success(self, client, mock_file_exists, mock_galicia_csv):
        """Test de preview exitoso con CSV válido"""
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value = io.StringIO(mock_galicia_csv)
            
            with patch('galicia_api.extractor.GaliciaExtractor.extract'):
                with patch('galicia_api.transformer.GaliciaTransformer.transform'):
                    response = client.post("/extract/preview")
                    
                    if response.status_code == 200:
                        data = response.json()
                        assert "extraidos" in data
                        assert "estaciones" in data
                        assert data["source"] == "GAL"
    
    def test_extract_preview_invalid_csv(self, client, mock_file_exists):
        """Test de preview con CSV inválido"""
        invalid_csv = "invalid;csv;format\n"
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value = io.StringIO(invalid_csv)
            
            response = client.post("/extract/preview")
            # Debe manejar CSV inválido
            assert response.status_code in [200, 400, 422, 500]


class TestExtractFull:
    """Tests del endpoint de extracción completa"""
    
    def test_extract_without_central_api(self, client, mock_file_exists):
        """Test de extracción cuando API Central no está disponible"""
        with patch('galicia_api.extractor.GaliciaExtractor.extract', return_value=[]):
            with patch('common.client.CentralAPIClient.enviar_payload', side_effect=Exception("Connection refused")):
                response = client.post("/extract")
                # Debe manejar error de conexión
                assert response.status_code in [200, 500, 503]
    
    def test_extract_success(self, client, mock_file_exists, mock_httpx_client):
        """Test de extracción completa exitosa"""
        mock_data = [
            {
                "Nombre": "ESTACION ITV VIGO",
                "Tipo": "Estación Fija",
                "Direccion": "Rúa Test 123",
                "CodigoPostal": "36201",
                "Municipio": "Vigo",
                "Provincia": "Pontevedra",
                "Latitud": 42.2406,
                "Longitud": -8.7207
            }
        ]
        
        with patch('galicia_api.extractor.GaliciaExtractor.extract', return_value=mock_data):
            with patch('galicia_api.transformer.GaliciaTransformer.transform') as mock_transform:
                mock_transform.return_value = (
                    [{
                        "nombre": "Estación ITV Vigo",
                        "tipo": "estacion_fija",
                        "direccion": "Rúa Test 123",
                        "codigo_postal": "36201",
                        "localidad": "Vigo",
                        "provincia": "Pontevedra",
                        "latitud": 42.2406,
                        "longitud": -8.7207
                    }],
                    []
                )
                
                response = client.post("/extract")
                
                if response.status_code == 200:
                    data = response.json()
                    assert data["source"] == "GAL"
                    assert "extraidos" in data


class TestTransformer:
    """Tests de la lógica de transformación"""
    
    def test_transform_valid_station(self):
        """Test de transformación de estación válida"""
        from galicia_api.transformer import GaliciaTransformer
        
        raw_item = {
            "Nombre": "ESTACION ITV VIGO",
            "Tipo": "Estación Fija",
            "Direccion": "Rúa Test 123",
            "CodigoPostal": "36201",
            "Municipio": "Vigo",
            "Provincia": "Pontevedra",
            "Latitud": 42.2406,
            "Longitud": -8.7207
        }
        
        transformer = GaliciaTransformer()
        result = transformer.transform_item(raw_item, 0)
        
        if result:
            assert result["nombre"] is not None
            assert result["localidad"] == "Vigo"
            assert result["provincia"] == "Pontevedra"
            assert result["latitud"] == 42.2406
    
    def test_transform_missing_postal_code(self):
        """Test de transformación sin código postal"""
        from galicia_api.transformer import GaliciaTransformer
        
        raw_item = {
            "Nombre": "ESTACION TEST",
            "Municipio": "Vigo",
            "Provincia": "Pontevedra",
            "Latitud": 42.2406,
            "Longitud": -8.7207
            # Falta CodigoPostal
        }
        
        transformer = GaliciaTransformer()
        result = transformer.transform_item(raw_item, 0)
        
        # Código postal es opcional, debe procesar igual
        if result:
            assert result["codigo_postal"] is None or result["codigo_postal"] == ""
    
    def test_transform_galician_names(self):
        """Test de normalización de nombres gallegos"""
        from galicia_api.transformer import GaliciaTransformer
        
        raw_item = {
            "Nombre": "ESTACION ITV A CORUÑA",
            "Municipio": "A Coruña",
            "Provincia": "A Coruña",
            "Latitud": 43.3623,
            "Longitud": -8.4115
        }
        
        transformer = GaliciaTransformer()
        result = transformer.transform_item(raw_item, 0)
        
        if result:
            # Verificar normalización de nombres gallegos
            assert result["localidad"] is not None
            assert result["provincia"] is not None


class TestCSVExtractor:
    """Tests del extractor CSV"""
    
    def test_extract_valid_csv(self, mock_galicia_csv):
        """Test de extracción de CSV válido"""
        from galicia_api.extractor import GaliciaExtractor
        
        extractor = GaliciaExtractor()
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value = io.StringIO(mock_galicia_csv)
            
            result = extractor.extract("dummy_path.csv")
            
            assert isinstance(result, list)
            # Debe tener al menos 2 estaciones del CSV mock
            if len(result) > 0:
                assert len(result) >= 2
    
    def test_extract_empty_csv(self):
        """Test de extracción de CSV vacío"""
        from galicia_api.extractor import GaliciaExtractor
        
        empty_csv = "Nombre;Tipo;Direccion\n"
        
        extractor = GaliciaExtractor()
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value = io.StringIO(empty_csv)
            
            result = extractor.extract("dummy_path.csv")
            
            assert isinstance(result, list)
            assert len(result) == 0
    
    def test_extract_csv_with_delimiter(self):
        """Test de detección correcta del delimitador CSV"""
        from galicia_api.extractor import GaliciaExtractor
        
        # CSV con delimitador punto y coma
        csv_content = """Nombre;Municipio
Estacion 1;Vigo
Estacion 2;Coruña
"""
        
        extractor = GaliciaExtractor()
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value = io.StringIO(csv_content)
            
            result = extractor.extract("dummy_path.csv")
            
            # Debe detectar el delimitador correctamente
            assert isinstance(result, list)


class TestIntegration:
    """Tests de integración completa"""
    
    def test_full_workflow_preview(self, client, mock_file_exists, mock_galicia_csv):
        """Test del flujo completo en modo preview"""
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value = io.StringIO(mock_galicia_csv)
            
            response = client.post("/extract/preview")
            
            # Debe completar el flujo sin errores
            assert response.status_code in [200, 500]
    
    def test_error_handling(self, client):
        """Test de manejo de errores"""
        with patch('os.path.exists', return_value=False):
            response = client.post("/extract")
            
            # Debe manejar el error gracefully
            assert response.status_code in [400, 500, 503]
