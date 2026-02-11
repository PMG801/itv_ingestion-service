"""
Tests de los schemas compartidos entre microservicios
"""
import pytest
from datetime import datetime
from pydantic import ValidationError


class TestEstacionExtraidaSchema:
    """Tests del modelo EstacionExtraida"""
    
    def test_create_valid_estacion(self):
        """Test de creación de estación válida"""
        from extractor_services.common.schemas import EstacionExtraida, TipoEstacion
        
        estacion = EstacionExtraida(
            nombre="Estación Test",
            tipo=TipoEstacion.ESTACION_FIJA,
            direccion="Calle Test 123",
            codigo_postal="46001",
            localidad="Valencia",
            provincia="Valencia",
            latitud=39.4699,
            longitud=-0.3763,
            horario="L-V 8:00-20:00",
            contacto="test@itv.es",
            url="https://test.com"
        )
        
        assert estacion.nombre == "Estación Test"
        assert estacion.tipo == TipoEstacion.ESTACION_FIJA
        assert estacion.latitud == 39.4699
        assert estacion.codigo_postal == "46001"
    
    def test_estacion_missing_required_fields(self):
        """Test de validación con campos requeridos faltantes"""
        from extractor_services.common.schemas import EstacionExtraida
        
        with pytest.raises(ValidationError):
            EstacionExtraida(
                nombre="Test"
                # Faltan: localidad, provincia, latitud, longitud
            )
    
    def test_estacion_invalid_coordinates(self):
        """Test de validación con coordenadas fuera de rango"""
        from extractor_services.common.schemas import EstacionExtraida
        
        with pytest.raises(ValidationError):
            EstacionExtraida(
                nombre="Test",
                localidad="Valencia",
                provincia="Valencia",
                latitud=999,  # Fuera de rango [-90, 90]
                longitud=-0.3763
            )
    
    def test_estacion_optional_fields(self):
        """Test de campos opcionales"""
        from extractor_services.common.schemas import EstacionExtraida
        
        estacion = EstacionExtraida(
            nombre="Test",
            localidad="Valencia",
            provincia="Valencia",
            latitud=39.4699,
            longitud=-0.3763
            # Campos opcionales omitidos
        )
        
        assert estacion.direccion is None
        assert estacion.codigo_postal is None
        assert estacion.horario is None


class TestPayloadExtraccionSchema:
    """Tests del modelo PayloadExtraccion"""
    
    def test_create_valid_payload(self, sample_payload):
        """Test de creación de payload válido"""
        from extractor_services.common.schemas import PayloadExtraccion
        
        payload = PayloadExtraccion(**sample_payload)
        
        assert payload.source == "VAL"
        assert len(payload.estaciones) == 2
        assert payload.stats.transformados == 2
    
    def test_payload_empty_estaciones(self):
        """Test de payload sin estaciones"""
        from extractor_services.common.schemas import PayloadExtraccion
        
        payload = PayloadExtraccion(
            source="VAL",
            timestamp=datetime.now(),
            estaciones=[],
            rechazados=[],
            stats={
                "total_raw": 0,
                "transformados": 0,
                "rechazados": 0
            }
        )
        
        assert len(payload.estaciones) == 0
        assert payload.stats.total_raw == 0
    
    def test_payload_with_rechazados(self):
        """Test de payload con registros rechazados"""
        from extractor_services.common.schemas import (
            PayloadExtraccion,
            EstacionExtraida,
            RegistroRechazado,
            EstadisticasExtraccion
        )
        
        payload = PayloadExtraccion(
            source="CAT",
            timestamp=datetime.now(),
            estaciones=[
                EstacionExtraida(
                    nombre="Válida",
                    localidad="Barcelona",
                    provincia="Barcelona",
                    latitud=41.3851,
                    longitud=2.1734
                )
            ],
            rechazados=[
                RegistroRechazado(
                    registro=2,
                    nombre="Inválida",
                    razon="Coordenadas faltantes"
                )
            ],
            stats=EstadisticasExtraccion(
                total_raw=2,
                transformados=1,
                rechazados=1
            )
        )
        
        assert len(payload.estaciones) == 1
        assert len(payload.rechazados) == 1
        assert payload.rechazados[0].razon == "Coordenadas faltantes"


class TestIngestResponseSchema:
    """Tests del modelo IngestResponse"""
    
    def test_create_success_response(self):
        """Test de creación de respuesta exitosa"""
        from extractor_services.common.schemas import IngestResponse
        
        response = IngestResponse(
            status="success",
            source="VAL",
            recibidos=10,
            insertados=8,
            duplicados_detectados=2,
            errores_insercion=0,
            mensaje="Carga completada"
        )
        
        assert response.status == "success"
        assert response.insertados == 8
        assert response.duplicados_detectados == 2
    
    def test_response_default_values(self):
        """Test de valores por defecto en respuesta"""
        from extractor_services.common.schemas import IngestResponse
        
        response = IngestResponse(
            status="success",
            source="GAL",
            recibidos=5,
            insertados=5,
            mensaje="OK"
        )
        
        # Valores por defecto
        assert response.duplicados_detectados == 0
        assert response.errores_insercion == 0


class TestTipoEstacionEnum:
    """Tests del enum TipoEstacion"""
    
    def test_valid_tipos(self):
        """Test de tipos válidos"""
        from extractor_services.common.schemas import TipoEstacion
        
        assert TipoEstacion.ESTACION_FIJA == "estacion_fija"
        assert TipoEstacion.ESTACION_MOVIL == "estacion_movil"
        assert TipoEstacion.OTROS == "otros"
    
    def test_tipo_in_estacion(self):
        """Test de uso de tipo en estación"""
        from extractor_services.common.schemas import EstacionExtraida, TipoEstacion
        
        estacion = EstacionExtraida(
            nombre="Test",
            tipo=TipoEstacion.ESTACION_MOVIL,
            localidad="Valencia",
            provincia="Valencia",
            latitud=39.4699,
            longitud=-0.3763
        )
        
        assert estacion.tipo == TipoEstacion.ESTACION_MOVIL
        assert estacion.tipo.value == "estacion_movil"


class TestSchemaSerializacion:
    """Tests de serialización/deserialización"""
    
    def test_estacion_to_dict(self, sample_estacion):
        """Test de conversión a diccionario"""
        from extractor_services.common.schemas import EstacionExtraida
        
        estacion = EstacionExtraida(**sample_estacion)
        estacion_dict = estacion.model_dump()
        
        assert isinstance(estacion_dict, dict)
        assert estacion_dict["nombre"] == sample_estacion["nombre"]
        assert estacion_dict["latitud"] == sample_estacion["latitud"]
    
    def test_payload_to_json(self, sample_payload):
        """Test de conversión a JSON"""
        from extractor_services.common.schemas import PayloadExtraccion
        
        payload = PayloadExtraccion(**sample_payload)
        json_str = payload.model_dump_json()
        
        assert isinstance(json_str, str)
        assert "VAL" in json_str
    
    def test_estacion_from_dict(self, sample_estacion):
        """Test de creación desde diccionario"""
        from extractor_services.common.schemas import EstacionExtraida
        
        estacion = EstacionExtraida.model_validate(sample_estacion)
        
        assert estacion.nombre == sample_estacion["nombre"]
        assert estacion.latitud == sample_estacion["latitud"]
