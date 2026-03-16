"""
Catalunya XML data transformer.

Handles XML format data from Catalunya's ITV system.
"""

import logging
import xml.etree.ElementTree as ET
from typing import List, Any, Union, Dict

from domain.itv_stations.transformers.base import BaseTransformer
from domain.itv_stations.schemas import NormalizedStation

logger = logging.getLogger(__name__)


class CatalunyaTransformer(BaseTransformer):
    """
    Transforms Catalunya XML data to normalized format.
    
    Catalunya provides ITV station data in XML format with Catalan field names.
    This transformer parses the XML and maps fields to the universal schema.
    
    Expected XML structure:
        <stations>
            <station>
                <id>BCN-001</id>
                <nom>ITV Barcelona Nord</nom>
                <adreca>Carrer de la Indústria 123</adreca>
                <ciutat>Barcelona</ciutat>
                <provincia>Barcelona</provincia>
                <codi_postal>08025</codi_postal>
                <latitud>41,3851</latitud>
                <longitud>2,1734</longitud>
                <telefon>932123456</telefon>
                <email>info@itv.cat</email>
            </station>
        </stations>
    """
    
    def __init__(self):
        """Initialize Catalunya transformer."""
        super().__init__(source_system="catalunya")
    
    def transform(self, raw_payload: Any) -> List[NormalizedStation]:
        """
        Parse Catalunya XML and extract ITV stations.
        
        Args:
            raw_payload: XML string or dict containing station data.
            
        Returns:
            List of NormalizedStation objects.
            
        Raises:
            ValueError: If XML is malformed or cannot be parsed.
        """
        # Handle dict payload (for testing or pre-parsed data)
        if isinstance(raw_payload, dict):
            return self._transform_dict(raw_payload)
        
        # Handle list of dicts (for testing with multiple stations)
        if isinstance(raw_payload, list):
            return self._transform_list(raw_payload)
        
        # Parse XML string
        try:
            root = ET.fromstring(raw_payload)
        except ET.ParseError as e:
            logger.error(f"Failed to parse Catalunya XML: {e}")
            raise ValueError(f"Invalid XML format: {e}")
        
        stations = []
        
        # Find all station elements
        for station_elem in root.findall("station"):
            try:
                station = self._transform_station_element(station_elem)
                if station:
                    stations.append(station)
            except Exception as e:
                # Log error but continue processing other stations
                raw_id = station_elem.findtext("id", "unknown")
                logger.warning(
                    f"Failed to transform Catalunya station {raw_id}: {e}"
                )
                continue
        
        logger.info(f"Transformed {len(stations)} stations from Catalunya")
        return stations
    
    def _transform_station_element(self, elem: ET.Element) -> NormalizedStation | None:
        """
        Transform a single XML station element to NormalizedStation.
        
        Args:
            elem: XML Element representing a station.
            
        Returns:
            NormalizedStation object or None if validation fails.
        """
        raw_id = elem.findtext("id", "").strip()
        
        if not raw_id:
            logger.warning("Skipping station without ID")
            return None
        
        # Extract and normalize data
        station_data = {
            "station_id": self._generate_station_id(raw_id),
            "name": elem.findtext("nom", "").strip(),
            "address": elem.findtext("adreca"),
            "city": elem.findtext("ciutat"),
            "province": elem.findtext("provincia"),
            "postal_code": self._clean_postal_code(elem.findtext("codi_postal")),
            "latitude": self._parse_float(elem.findtext("latitud")),
            "longitude": self._parse_float(elem.findtext("longitud")),
            "phone": self._clean_phone(elem.findtext("telefon")),
            "email": elem.findtext("email"),
            "source_system": self.source_system,
            "raw_id": raw_id,
        }
        
        # Validate and create NormalizedStation
        try:
            return NormalizedStation(**station_data)
        except Exception as e:
            logger.error(f"Validation failed for station {raw_id}: {e}")
            return None
    
    def _transform_dict(self, payload: Dict) -> List[NormalizedStation]:
        """
        Transform dict payload (for testing or JSON-like data).
        
        Args:
            payload: Dictionary with station data or stations list.
            
        Returns:
            List of NormalizedStation objects.
        """
        # Handle single station
        if "id" in payload or "nom" in payload:
            station = self._transform_dict_station(payload)
            return [station] if station else []
        
        # Handle multiple stations
        if "stations" in payload:
            return self._transform_list(payload["stations"])
        
        # Handle list at root
        if isinstance(payload, dict) and len(payload) == 0:
            return []
        
        logger.warning(f"Unexpected Catalunya payload structure: {payload.keys()}")
        return []
    
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
                station = self._transform_dict_station(station_dict)
                if station:
                    stations.append(station)
            except Exception as e:
                raw_id = station_dict.get("id", "unknown")
                logger.warning(f"Failed to transform station {raw_id}: {e}")
                continue
        
        return stations
    
    def _transform_dict_station(self, data: Dict) -> NormalizedStation | None:
        """
        Transform a single station dictionary to NormalizedStation.
        
        Args:
            data: Dictionary with station data.
            
        Returns:
            NormalizedStation object or None if validation fails.
        """
        raw_id = data.get("id", "").strip()
        
        if not raw_id:
            logger.warning("Skipping station without ID")
            return None
        
        # Map Catalan field names to normalized schema
        station_data = {
            "station_id": self._generate_station_id(raw_id),
            "name": data.get("nom", "").strip(),
            "address": data.get("adreca"),
            "city": data.get("ciutat"),
            "province": data.get("provincia"),
            "postal_code": self._clean_postal_code(data.get("codi_postal")),
            "latitude": self._parse_float(data.get("latitud")),
            "longitude": self._parse_float(data.get("longitud")),
            "phone": self._clean_phone(data.get("telefon")),
            "email": data.get("email"),
            "source_system": self.source_system,
            "raw_id": raw_id,
        }
        
        try:
            return NormalizedStation(**station_data)
        except Exception as e:
            logger.error(f"Validation failed for station {raw_id}: {e}")
            return None
