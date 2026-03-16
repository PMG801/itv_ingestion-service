"""
Galicia CSV data transformer.

Handles CSV format data from Galicia's ITV system.
"""

import logging
import csv
from io import StringIO
from typing import List, Any, Dict

from domain.itv_stations.transformers.base import BaseTransformer
from domain.itv_stations.schemas import NormalizedStation

logger = logging.getLogger(__name__)


class GaliciaTransformer(BaseTransformer):
    """
    Transforms Galicia CSV data to normalized format.
    
    Galicia provides ITV station data in CSV format with Galician/Spanish
    field names. This transformer parses the CSV and maps fields to the
    universal schema.
    
    Expected CSV structure:
        id,nome,enderezo,concello,provincia,cp,lat,lon,telefono,email
        LU-001,ITV Lugo Centro,Rúa da Industria 789,Lugo,Lugo,27001,43.0097,-7.5567,982123456,info@itvlugo.gal
    
    Alternative field names (Galician):
        - nome/nombre: name
        - enderezo/direccion: address
        - concello/poblacion: city
        - cp/codigo_postal: postal_code
        - lat/latitud/latitude: latitude
        - lon/longitud/longitude: longitude
        - telefono/phone: phone
        - email/correo: email
    """
    
    def __init__(self):
        """Initialize Galicia transformer."""
        super().__init__(source_system="galicia")
    
    def transform(self, raw_payload: Any) -> List[NormalizedStation]:
        """
        Parse Galicia CSV and extract ITV stations.
        
        Args:
            raw_payload: CSV string, list of dicts, or dict containing station data.
            
        Returns:
            List of NormalizedStation objects.
            
        Raises:
            ValueError: If CSV is malformed or cannot be parsed.
        """
        # Handle pre-parsed list of dicts (for testing)
        if isinstance(raw_payload, list):
            return self._transform_list(raw_payload)
        
        # Handle single dict (for testing)
        if isinstance(raw_payload, dict):
            if "stations" in raw_payload or "estaciones" in raw_payload:
                stations_list = raw_payload.get("stations") or raw_payload.get("estaciones")
                return self._transform_list(stations_list)
            else:
                # Single station dict
                station = self._transform_station(raw_payload)
                return [station] if station else []
        
        # Handle CSV string
        if isinstance(raw_payload, str):
            return self._parse_csv(raw_payload)
        
        logger.error(f"Invalid Galicia payload type: {type(raw_payload)}")
        raise ValueError(f"Expected string, list, or dict, got {type(raw_payload)}")
    
    def _parse_csv(self, csv_string: str) -> List[NormalizedStation]:
        """
        Parse CSV string and extract stations.
        
        Args:
            csv_string: CSV formatted string with station data.
            
        Returns:
            List of NormalizedStation objects.
        """
        try:
            # Create CSV reader
            csv_file = StringIO(csv_string.strip())
            reader = csv.DictReader(csv_file)
            
            stations = []
            for row in reader:
                try:
                    station = self._transform_station(row)
                    if station:
                        stations.append(station)
                except Exception as e:
                    raw_id = row.get("id", "unknown")
                    logger.warning(f"Failed to transform Galicia station {raw_id}: {e}")
                    continue
            
            logger.info(f"Transformed {len(stations)} stations from Galicia")
            return stations
            
        except Exception as e:
            logger.error(f"Failed to parse Galicia CSV: {e}")
            raise ValueError(f"Invalid CSV format: {e}")
    
    def _transform_list(self, stations_list: List[Dict]) -> List[NormalizedStation]:
        """
        Transform list of station dictionaries.
        
        Args:
            stations_list: List of station data dictionaries.
            
        Returns:
            List of NormalizedStation objects.
        """
        stations = []
        
        for station_dict in stations_list:
            try:
                station = self._transform_station(station_dict)
                if station:
                    stations.append(station)
            except Exception as e:
                raw_id = station_dict.get("id", "unknown")
                logger.warning(f"Failed to transform Galicia station {raw_id}: {e}")
                continue
        
        logger.info(f"Transformed {len(stations)} stations from Galicia")
        return stations
    
    def _transform_station(self, data: Dict) -> NormalizedStation | None:
        """
        Transform a single station dictionary to NormalizedStation.
        
        Args:
            data: Dictionary with station data (from CSV row or dict).
            
        Returns:
            NormalizedStation object or None if validation fails.
        """
        # Get raw ID from various possible fields
        raw_id = (
            data.get("id") or
            data.get("codigo") or
            data.get("station_id") or
            ""
        ).strip()
        
        if not raw_id:
            logger.warning("Skipping Galicia station without ID")
            return None
        
        # Map Galician field names to normalized schema
        # Support both Galician and Spanish field names
        station_data = {
            "station_id": self._generate_station_id(raw_id),
            "name": (
                data.get("nome") or
                data.get("nombre") or
                data.get("name") or
                ""
            ).strip(),
            "address": (
                data.get("enderezo") or
                data.get("direccion") or
                data.get("address")
            ),
            "city": (
                data.get("concello") or
                data.get("poblacion") or
                data.get("ciudad") or
                data.get("city")
            ),
            "province": (
                data.get("provincia") or
                data.get("province")
            ),
            "postal_code": self._clean_postal_code(
                data.get("cp") or
                data.get("codigo_postal") or
                data.get("postal_code")
            ),
            "latitude": self._parse_float(
                data.get("lat") or
                data.get("latitud") or
                data.get("latitude")
            ),
            "longitude": self._parse_float(
                data.get("lon") or
                data.get("longitud") or
                data.get("longitude")
            ),
            "phone": self._clean_phone(
                data.get("telefono") or
                data.get("phone")
            ),
            "email": (
                data.get("email") or
                data.get("correo")
            ),
            "source_system": self.source_system,
            "raw_id": raw_id,
        }
        
        try:
            return NormalizedStation(**station_data)
        except Exception as e:
            logger.error(f"Validation failed for Galicia station {raw_id}: {e}")
            return None
