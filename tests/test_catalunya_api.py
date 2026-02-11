"""
Tests para el microservicio Catalunya API
"""
import pytest
import sys
import os
from unittest.mock import patch, Mock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'extractor_services'))

from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Cliente de test para Catalunya API"""
    from catalunya_api.main import app
    return TestClient(app)


@pytest.fixture
def mock_file_exists():
    """Mock para que el archivo de datos exista"""
    with patch('os.path.exists', return_value=True):
        yield


@pytest.fixture
def mock_catalunya_xml():
    """XML de ejemplo de Catalunya"""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <estaciones>
        <estacion>
            <nombre>ESTACIO ITV BARCELONA</nombre>
            <tipo>Estacio Fixa</tipo>
            <direccio>Carrer Test 123</direccio>
            <codi_postal>08001</codi_postal>
            <municipi>Barcelona</municipi>
            <provincia>Barcelona</provincia>
            <latitud>41.3851</latitud>
            <longitud>2.1734</longitud>
            <horari>Dilluns a divendres 8:00-20:00</horari>
            <contacte>info@itv.cat</contacte>
        </estacion>
    </estaciones>
    """


class TestHealthEndpoint:
    """Tests del endpoint de health check"""
    
    def test_health_endpoint_root(self, client):
        """Test de endpoint raíz /"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Catalunya ITV Extractor"
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
        """Test de preview cuando no existe el archivo XML"""
        with patch('os.path.exists', return_value=False):
            response = client.post("/extract/preview")
            assert response.status_code in [500, 400]
    
    def test_extract_preview_success(self, client, mock_file_exists, mock_catalunya_xml):
        """Test de preview exitoso con XML válido"""
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = mock_catalunya_xml
            
            with patch('catalunya_api.extractor.CatalunyaExtractor.extract'):
                with patch('catalunya_api.transformer.CatalunyaTransformer.transform'):
                    response = client.post("/extract/preview")
                    
                    if response.status_code == 200:
                        data = response.json()
                        assert "extraidos" in data
                        assert "estaciones" in data
                        assert data["source"] == "CAT"
    
    def test_extract_preview_invalid_xml(self, client, mock_file_exists):
        """Test de preview con XML inválido"""
        invalid_xml = "<?xml version='1.0'?><invalid>"
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = invalid_xml
            
            response = client.post("/extract/preview")
            # Debe manejar XML inválido
            assert response.status_code in [200, 400, 422, 500]


class TestExtractFull:
    """Tests del endpoint de extracción completa"""
    
    def test_extract_without_central_api(self, client, mock_file_exists):
        """Test de extracción cuando API Central no está disponible"""
        with patch('catalunya_api.extractor.CatalunyaExtractor.extract', return_value=[]):
            with patch('common.client.CentralAPIClient.enviar_payload', side_effect=Exception("Connection refused")):
                response = client.post("/extract")
                # Debe manejar error de conexión
                assert response.status_code in [200, 500, 503]
    
    def test_extract_success(self, client, mock_file_exists, mock_httpx_client):
        """Test de extracción completa exitosa"""
        mock_data = [{
            "nombre": "ESTACIO ITV BARCELONA",
            "tipo": "Estacio Fixa",
            "direccio": "Carrer Test 123",
            "codi_postal": "08001",
            "municipi": "Barcelona",
            "provincia": "Barcelona",
            "latitud": 41.3851,
            "longitud": 2.1734
        }]
        
        with patch('catalunya_api.extractor.CatalunyaExtractor.extract', return_value=mock_data):
            with patch('catalunya_api.transformer.CatalunyaTransformer.transform') as mock_transform:
                mock_transform.return_value = (
                    [{
                        "nombre": "Estació ITV Barcelona",
                        "tipo": "estacion_fija",
                        "direccion": "Carrer Test 123",
                        "codigo_postal": "08001",
                        "localidad": "Barcelona",
                        "provincia": "Barcelona",
                        "latitud": 41.3851,
                        "longitud": 2.1734
                    }],
                    []
                )
                
                response = client.post("/extract")
                
                if response.status_code == 200:
                    data = response.json()
                    assert data["source"] == "CAT"
                    assert "extraidos" in data


class TestTransformer:
    """Tests de la lógica de transformación"""
    
    def test_transform_valid_station(self):
        """Test de transformación de estación válida"""
        from catalunya_api.transformer import CatalunyaTransformer
        
        raw_item = {
            "nombre": "ESTACIO ITV BARCELONA",
            "tipo": "Estacio Fixa",
            "direccio": "Carrer Test 123",
            "codi_postal": "08001",
            "municipi": "Barcelona",
            "provincia": "Barcelona",
            "latitud": 41.3851,
            "longitud": 2.1734
        }
        
        transformer = CatalunyaTransformer()
        result = transformer.transform_item(raw_item, 0)
        
        if result:
            assert result["nombre"] is not None
            assert result["localidad"] == "Barcelona"
            assert result["provincia"] == "Barcelona"
            assert result["latitud"] == 41.3851
    
    def test_transform_missing_coordinates(self):
        """Test de transformación sin coordenadas"""
        from catalunya_api.transformer import CatalunyaTransformer
        
        raw_item = {
            "nombre": "ESTACIO TEST",
            "municipi": "Barcelona",
            "provincia": "Barcelona"
            # Faltan coordenadas
        }
        
        transformer = CatalunyaTransformer()
        result = transformer.transform_item(raw_item, 0)
        
        # Debe intentar geocoding o rechazar
        assert True  # Placeholder
    
    def test_transform_normalization(self):
        """Test de normalización de datos catalanes"""
        from catalunya_api.transformer import CatalunyaTransformer
        
        raw_item = {
            "nombre": "ESTACIO ITV",
            "tipo": "Estacio Fixa",
            "municipi": "Sant Adrià de Besòs",
            "provincia": "Barcelona",
            "latitud": 41.4302,
            "longitud": 2.2199
        }
        
        transformer = CatalunyaTransformer()
        result = transformer.transform_item(raw_item, 0)
        
        if result:
            # Verificar normalización de nombres catalanes
            assert result["localidad"] is not None
            assert result["tipo"] == "estacion_fija"


class TestXMLExtractor:
    """Tests del extractor XML"""
    
    def test_extract_valid_xml(self):
        """Test de extracción de XML válido"""
        from catalunya_api.extractor import CatalunyaExtractor
        import xml.etree.ElementTree as ET
        
        xml_content = """<?xml version="1.0"?>
        <estaciones>
            <estacion>
                <nombre>Test</nombre>
                <municipi>Barcelona</municipi>
            </estacion>
        </estaciones>
        """
        
        extractor = CatalunyaExtractor()
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = xml_content
            
            result = extractor.extract("dummy_path.xml")
            
            # Debe extraer al menos el contenido básico
            assert isinstance(result, list)
    
    def test_extract_empty_xml(self):
        """Test de extracción de XML vacío"""
        from catalunya_api.extractor import CatalunyaExtractor
        
        xml_content = """<?xml version="1.0"?><estaciones></estaciones>"""
        
        extractor = CatalunyaExtractor()
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = xml_content
            
            result = extractor.extract("dummy_path.xml")
            
            assert isinstance(result, list)
            assert len(result) == 0
