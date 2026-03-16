"""
Valencia JSON data transformer.

Handles JSON format data from Valencia's ITV system.
"""

import logging
from typing import List, Any, Dict, Union

from domain.itv_stations.transformers.base import BaseTransformer
from domain.itv_stations.schemas import NormalizedStation

logger = logging.getLogger(__name__)


class ValenciaTransformer(BaseTransformer):
    """
    Transforms Valencia JSON data to normalized format.
    
    Valencia provides ITV station data in JSON format with Valencian/Spanish
    field names. This transformer parses the JSON and maps fields to the
    universal schema.
    
    Expected JSON structure:
        {
            "estaciones": [
                {
                    "codigo": "VAL-042",
                    "nombre": "ITV Valencia Norte",
                    "direccion": "Calle de la Industria 456",
                    "poblacion": "Valencia",
                    "provincia": "Valencia",
                    "codigo_postal": "46015",
                    "latitud": 39.4699,
                    "longitud": -0.3763,
                    "telefono": "963456789",
                    "correo": "contacto@itvvalencia.es"
                }
            ]
        }
    """
    
    def __init__(self):
        """Initialize Valencia transformer."""
        super().__init__(source_system="valencia")
    
    def transform(self, raw_payload: Any) -> List[NormalizedStation]:
        """
        Parse Valencia JSON and extract ITV stations.
        
        Args:
            raw_payload: Dict or list containing station data.
            
        Returns:
            List of NormalizedStation objects.
            
        Raises:
            ValueError: If payload structure is invalid.
        """
        # Handle dict with "estaciones" key
        if isinstance(raw_payload, dict):
            if "estaciones" in raw_payload:
                stations_list = raw_payload["estaciones"]
            elif "stations" in raw_payload:
                # Alternative English key
                stations_list = raw_payload["stations"]
            elif "codigo" in raw_payload or "nombre" in raw_payload:
                # Single station dict
                station = self._transform_station(raw_payload)
                return [station] if station else []
            else:
                logger.warning(f"Unexpected Valencia payload structure: {raw_payload.keys()}")
                return []
        
        # Handle direct list
        elif isinstance(raw_payload, list):
            stations_list = raw_payload
        
        else:
            logger.error(f"Invalid Valencia payload type: {type(raw_payload)}")
            raise ValueError(f"Expected dict or list, got {type(raw_payload)}")
        
        # Transform each station
        stations = []
        for station_data in stations_list:
            try:
                station = self._transform_station(station_data)
                if station:
                    stations.append(station)
            except Exception as e:
                raw_id = station_data.get("codigo", "unknown")
                logger.warning(f"Failed to transform Valencia station {raw_id}: {e}")
                continue
        
        logger.info(f"Transformed {len(stations)} stations from Valencia")
        return stations
    
    def _transform_station(self, data: Dict) -> NormalizedStation | None:
        """
        Transform a single station dictionary to NormalizedStation.
        
        Args:
            data: Dictionary with station data.
            
        Returns:
            NormalizedStation object or None if validation fails.
        """
        # Get raw ID from various possible fields
        raw_id = (
            data.get("codigo") or
            data.get("id") or
            data.get("station_id") or
            ""
        ).strip()
        
        if not raw_id:
            logger.warning("Skipping Valencia station without ID")
            return None
        
        # Map Valencia field names to normalized schema
        station_data = {
            "station_id": self._generate_station_id(raw_id),
            "name": (
                data.get("nombre") or
                data.get("name") or
                ""
            ).strip(),
            "address": data.get("direccion") or data.get("address"),
            "city": data.get("poblacion") or data.get("ciudad") or data.get("city"),
            "province": data.get("provincia") or data.get("province"),
            "postal_code": self._clean_postal_code(
                data.get("codigo_postal") or data.get("cp") or data.get("postal_code")
            ),
            "latitude": self._parse_float(data.get("latitud") or data.get("latitude")),
            "longitude": self._parse_float(data.get("longitud") or data.get("longitude")),
            "phone": self._clean_phone(
                data.get("telefono") or data.get("phone")
            ),
            "email": data.get("correo") or data.get("email"),
            "source_system": self.source_system,
            "raw_id": raw_id,
        }
        
        try:
            return NormalizedStation(**station_data)
        except Exception as e:
            logger.error(f"Validation failed for Valencia station {raw_id}: {e}")
            return None
