"""
Valencia JSON data transformer.

Handles JSON format data from Valencia's ITV system.
"""

import logging
from collections.abc import Mapping
from typing import Any, cast

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
    
    def transform(self, raw_payload: Any) -> list[NormalizedStation]:
        """
        Parse Valencia JSON and extract ITV stations.
        
        Args:
            raw_payload: Dict or list containing station data.
            
        Returns:
            List of NormalizedStation objects.
            
        Raises:
            ValueError: If payload structure is invalid.
        """
        self.reset_rejections()

        # Handle dict with "estaciones" key
        if isinstance(raw_payload, dict):
            payload_dict = cast(dict[str, object], raw_payload)
            stations_list: list[object] | None = None
            if "estaciones" in payload_dict:
                estaciones_value: object = payload_dict["estaciones"]
                if isinstance(estaciones_value, list):
                    stations_list = list(estaciones_value)
            elif "stations" in payload_dict:
                # Alternative English key
                stations_value: object = payload_dict["stations"]
                if isinstance(stations_value, list):
                    stations_list = list(stations_value)
            elif "codigo" in payload_dict or "nombre" in payload_dict:
                # Single station dict
                station = self._transform_station(payload_dict)
                return [station] if station else []
            else:
                logger.warning(f"Unexpected Valencia payload structure: {payload_dict.keys()}")
                return []
        
        # Handle direct list
        elif isinstance(raw_payload, list):
            stations_list = list(raw_payload)
        
        else:
            logger.error(f"Invalid Valencia payload type: {type(raw_payload)}")
            raise ValueError(f"Expected dict or list, got {type(raw_payload)}")
        
        if stations_list is None:
            return []

        # Transform each station
        stations: list[NormalizedStation] = []
        for station_data in stations_list:
            if not isinstance(station_data, dict):
                logger.warning("Skipping Valencia station with invalid payload type")
                self.record_rejection(
                    reason="invalid_station_payload_type",
                    raw_fragment={"value": str(station_data)},
                )
                continue
            try:
                station = self._transform_station(station_data)
                if station:
                    stations.append(station)
            except Exception as e:
                raw_id = self._as_optional_str(station_data.get("codigo")) or "unknown"
                logger.warning(f"Failed to transform Valencia station {raw_id}: {e}")
                self.record_rejection(
                    reason="station_transform_exception",
                    raw_fragment=dict(station_data),
                )
                continue
        
        # Apply deduplication checks
        stations = self._check_duplicate_within_message(stations)
        stations = self._check_duplicate_contact_fields(stations)
        
        logger.info(f"Transformed {len(stations)} stations from Valencia")
        return stations
    
    def _transform_station(self, data: Mapping[str, object]) -> NormalizedStation | None:
        """
        Transform a single station dictionary to NormalizedStation.
        
        Args:
            data: Dictionary with station data.
            
        Returns:
            NormalizedStation object or None if validation fails.
        """
        # Get raw ID from various possible fields
        raw_id = self._as_optional_str(
            data.get("codigo") or data.get("id") or data.get("station_id")
        ) or ""
        
        if not raw_id:
            logger.warning("Skipping Valencia station without ID")
            self.record_rejection(
                reason="missing_raw_id",
                raw_fragment=dict(data),
            )
            return None
        
        # Map Valencia field names to normalized schema
        try:
            station = NormalizedStation(
                station_id=self._generate_station_id(raw_id),
                name=self._as_optional_str(data.get("nombre") or data.get("name")) or "",
                address=self._as_optional_str(data.get("direccion") or data.get("address")),
                city=self._as_optional_str(data.get("poblacion") or data.get("ciudad") or data.get("city")),
                province=self._as_optional_str(data.get("provincia") or data.get("province")),
                postal_code=self._clean_postal_code(
                    self._as_optional_str(data.get("codigo_postal") or data.get("cp") or data.get("postal_code"))
                ),
                latitude=self._parse_float(data.get("latitud") or data.get("latitude")),
                longitude=self._parse_float(data.get("longitud") or data.get("longitude")),
                phone=self._clean_phone(self._as_optional_str(data.get("telefono") or data.get("phone"))),
                email=self._as_optional_str(data.get("correo") or data.get("email")),
                source_system="valencia",
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
            logger.error(f"Validation failed for Valencia station {raw_id}: {e}")
            self.record_rejection(
                reason="schema_validation_failed",
                raw_fragment=dict(data),
            )
            return None
