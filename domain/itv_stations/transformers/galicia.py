"""
Galicia CSV data transformer.

Handles CSV format data from Galicia's ITV system.
"""

import logging
import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any, cast

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
    
    def transform(self, raw_payload: Any) -> list[NormalizedStation]:
        """
        Parse Galicia CSV and extract ITV stations.
        
        Args:
            raw_payload: CSV string, list of dicts, or dict containing station data.
            
        Returns:
            List of NormalizedStation objects.
            
        Raises:
            ValueError: If CSV is malformed or cannot be parsed.
        """
        self.reset_rejections()

        # Handle pre-parsed list of dicts (for testing)
        if isinstance(raw_payload, list):
            return self._transform_list(raw_payload)
        
        # Handle single dict (for testing)
        if isinstance(raw_payload, dict):
            payload_dict = cast(dict[str, object], raw_payload)
            if "stations" in payload_dict or "estaciones" in payload_dict:
                stations_list_obj: object = payload_dict.get("stations") or payload_dict.get("estaciones")
                if not isinstance(stations_list_obj, list):
                    return []
                return self._transform_list(stations_list_obj)
            else:
                # Single station dict
                station = self._transform_station(payload_dict)
                return [station] if station else []
        
        # Handle CSV string
        if isinstance(raw_payload, str):
            return self._parse_csv(raw_payload)
        
        logger.error(f"Invalid Galicia payload type: {type(raw_payload)}")
        raise ValueError(f"Expected string, list, or dict, got {type(raw_payload)}")
    
    def _parse_csv(self, csv_string: str) -> list[NormalizedStation]:
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
            
            stations: list[NormalizedStation] = []
            for row in reader:
                try:
                    station = self._transform_station(row)
                    if station:
                        stations.append(station)
                except Exception as e:
                    raw_id = row.get("id", "unknown")
                    logger.warning(f"Failed to transform Galicia station {raw_id}: {e}")
                    self.record_rejection(
                        reason="station_transform_exception",
                        raw_fragment=dict(row),
                    )
                    continue
            
            # Apply deduplication checks
            stations = self._check_duplicate_within_message(stations)
            stations = self._check_duplicate_contact_fields(stations)
            
            logger.info(f"Transformed {len(stations)} stations from Galicia")
            return stations
            
        except Exception as e:
            logger.error(f"Failed to parse Galicia CSV: {e}")
            raise ValueError(f"Invalid CSV format: {e}")
    
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
                logger.warning("Skipping Galicia station with invalid payload type")
                self.record_rejection(
                    reason="invalid_station_payload_type",
                    raw_fragment={"value": str(station_dict)},
                )
                continue
            try:
                station = self._transform_station(station_dict)
                if station:
                    stations.append(station)
            except Exception as e:
                raw_id = self._as_optional_str(station_dict.get("id")) or "unknown"
                logger.warning(f"Failed to transform Galicia station {raw_id}: {e}")
                self.record_rejection(
                    reason="station_transform_exception",
                    raw_fragment=dict(station_dict),
                )
                continue
        
        # Apply deduplication checks
        stations = self._check_duplicate_within_message(stations)
        stations = self._check_duplicate_contact_fields(stations)
        
        logger.info(f"Transformed {len(stations)} stations from Galicia")
        return stations
    
    def _transform_station(self, data: Mapping[str, object]) -> NormalizedStation | None:
        """
        Transform a single station dictionary to NormalizedStation.
        
        Args:
            data: Dictionary with station data (from CSV row or dict).
            
        Returns:
            NormalizedStation object or None if validation fails.
        """
        # Get raw ID from various possible fields
        raw_id = self._as_optional_str(
            data.get("id") or data.get("codigo") or data.get("station_id")
        ) or ""
        
        if not raw_id:
            logger.warning("Skipping Galicia station without ID")
            self.record_rejection(
                reason="missing_raw_id",
                raw_fragment=dict(data),
            )
            return None
        
        # Map Galician field names to normalized schema
        # Support both Galician and Spanish field names
        try:
            station = NormalizedStation(
                station_id=self._generate_station_id(raw_id),
                name=self._as_optional_str(data.get("nome") or data.get("nombre") or data.get("name")) or "",
                address=self._as_optional_str(data.get("enderezo") or data.get("direccion") or data.get("address")),
                city=self._as_optional_str(data.get("concello") or data.get("poblacion") or data.get("ciudad") or data.get("city")),
                province=self._as_optional_str(data.get("provincia") or data.get("province")),
                postal_code=self._clean_postal_code(
                    self._as_optional_str(data.get("cp") or data.get("codigo_postal") or data.get("postal_code"))
                ),
                latitude=self._parse_float(data.get("lat") or data.get("latitud") or data.get("latitude")),
                longitude=self._parse_float(data.get("lon") or data.get("longitud") or data.get("longitude")),
                phone=self._clean_phone(self._as_optional_str(data.get("telefono") or data.get("phone"))),
                email=self._as_optional_str(data.get("email") or data.get("correo")),
                source_system="galicia",
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
            logger.error(f"Validation failed for Galicia station {raw_id}: {e}")
            self.record_rejection(
                reason="schema_validation_failed",
                raw_fragment=dict(data),
            )
            return None
