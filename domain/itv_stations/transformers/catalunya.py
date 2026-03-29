"""
Catalunya XML data transformer.

Handles XML format data from Catalunya's ITV system.
"""

import logging
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Any

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
    
    def transform(self, raw_payload: Any) -> list[NormalizedStation]:
        """
        Parse Catalunya XML and extract ITV stations.
        
        Args:
            raw_payload: XML string or dict containing station data.
            
        Returns:
            List of NormalizedStation objects.
            
        Raises:
            ValueError: If XML is malformed or cannot be parsed.
        """
        self.reset_rejections()

        # Handle dict payload (for testing or pre-parsed data)
        if isinstance(raw_payload, dict):
            return self._transform_dict(raw_payload)
        
        # Handle list of dicts (for testing with multiple stations)
        if isinstance(raw_payload, list):
            return self._transform_list(raw_payload)

        if not isinstance(raw_payload, str):
            raise ValueError(f"Expected XML string, dict or list, got {type(raw_payload)}")
        
        # Parse XML string
        try:
            root = ET.fromstring(raw_payload)
        except ET.ParseError as e:
            logger.error(f"Failed to parse Catalunya XML: {e}")
            raise ValueError(f"Invalid XML format: {e}")
        
        stations: list[NormalizedStation] = []
        
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
                self.record_rejection(
                    reason="station_transform_exception",
                    raw_fragment=ET.tostring(station_elem, encoding="unicode"),
                )
                continue
        
        # Apply deduplication checks
        stations = self._check_duplicate_within_message(stations)
        stations = self._check_duplicate_contact_fields(stations)
        
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
            self.record_rejection(
                reason="missing_raw_id",
                raw_fragment=ET.tostring(elem, encoding="unicode"),
            )
            return None
        
        # Extract and normalize data
        # Validate and create NormalizedStation
        try:
            station = NormalizedStation(
                station_id=self._generate_station_id(raw_id),
                name=elem.findtext("nom", "").strip(),
                address=self._as_optional_str(elem.findtext("adreca")),
                city=self._as_optional_str(elem.findtext("ciutat")),
                province=self._as_optional_str(elem.findtext("provincia")),
                postal_code=self._clean_postal_code(elem.findtext("codi_postal")),
                latitude=self._parse_float(elem.findtext("latitud")),
                longitude=self._parse_float(elem.findtext("longitud")),
                phone=self._clean_phone(self._as_optional_str(elem.findtext("telefon"))),
                email=self._as_optional_str(elem.findtext("email")),
                source_system="catalunya",
                raw_id=raw_id,
            )

            # Apply validation rules
            is_valid, validation_reason = self._validate_station(station)
            if not is_valid:
                logger.warning(f"Station {raw_id} failed validation: {validation_reason}")
                self.record_rejection(
                    reason=validation_reason or "validation_failed",
                    raw_fragment=ET.tostring(elem, encoding="unicode"),
                )
                return None

            return station
        except Exception as e:
            logger.error(f"Validation failed for station {raw_id}: {e}")
            self.record_rejection(
                reason="schema_validation_failed",
                raw_fragment=ET.tostring(elem, encoding="unicode"),
            )
            return None
    
    def _transform_dict(self, payload: Mapping[str, object]) -> list[NormalizedStation]:
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
            stations = payload["stations"]
            if isinstance(stations, list):
                return self._transform_list(stations)
            return []
        
        # Handle list at root
        if len(payload) == 0:
            return []
        
        logger.warning(f"Unexpected Catalunya payload structure: {payload.keys()}")
        return []
    
    def _transform_list(self, stations_list: list[object]) -> list[NormalizedStation]:
        """
        Transform list of station dictionaries.
        
        Args:
            stations_list: List of station data dictionaries.
            
        Returns:
            List of NormalizedStation objects.
        """
        stations: list[NormalizedStation] = []
        
        for station_dict in stations_list:
            if not isinstance(station_dict, dict):
                logger.warning("Skipping Catalunya station with invalid payload type")
                self.record_rejection(
                    reason="invalid_station_payload_type",
                    raw_fragment={"value": str(station_dict)},
                )
                continue
            try:
                station = self._transform_dict_station(station_dict)
                if station:
                    stations.append(station)
            except Exception as e:
                raw_id = self._as_optional_str(station_dict.get("id")) or "unknown"
                logger.warning(f"Failed to transform station {raw_id}: {e}")
                self.record_rejection(
                    reason="station_transform_exception",
                    raw_fragment=dict(station_dict),
                )
                continue
        
        # Apply deduplication checks
        stations = self._check_duplicate_within_message(stations)
        stations = self._check_duplicate_contact_fields(stations)
        
        return stations
    
    def _transform_dict_station(self, data: Mapping[str, object]) -> NormalizedStation | None:
        """
        Transform a single station dictionary to NormalizedStation.
        
        Args:
            data: Dictionary with station data.
            
        Returns:
            NormalizedStation object or None if validation fails.
        """
        raw_id = self._as_optional_str(data.get("id")) or ""
        
        if not raw_id:
            logger.warning("Skipping station without ID")
            self.record_rejection(
                reason="missing_raw_id",
                raw_fragment=dict(data),
            )
            return None
        
        # Map Catalan field names to normalized schema
        try:
            station = NormalizedStation(
                station_id=self._generate_station_id(raw_id),
                name=self._as_optional_str(data.get("nom")) or "",
                address=self._as_optional_str(data.get("adreca")),
                city=self._as_optional_str(data.get("ciutat")),
                province=self._as_optional_str(data.get("provincia")),
                postal_code=self._clean_postal_code(self._as_optional_str(data.get("codi_postal"))),
                latitude=self._parse_float(data.get("latitud")),
                longitude=self._parse_float(data.get("longitud")),
                phone=self._clean_phone(self._as_optional_str(data.get("telefon"))),
                email=self._as_optional_str(data.get("email")),
                source_system="catalunya",
                raw_id=raw_id,
            )

            # Apply validation rules
            is_valid, validation_reason = self._validate_station(station)
            if not is_valid:
                logger.warning(f"Station {raw_id} failed validation: {validation_reason}")
                self.record_rejection(
                    reason=validation_reason or "validation_failed",
                    raw_fragment=dict(data),
                )
                return None

            return station
        except Exception as e:
            logger.error(f"Validation failed for station {raw_id}: {e}")
            self.record_rejection(
                reason="schema_validation_failed",
                raw_fragment=dict(data),
            )
            return None
