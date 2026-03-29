"""
Base transformer interface following Strategy Pattern.

This module defines the abstract base class that all source-specific
transformers must implement to ensure consistent data transformation.
"""

from abc import ABC, abstractmethod
from typing import Any

from domain.itv_stations.schemas import NormalizedStation
from domain.itv_stations.rules import ITVValidationRules


class BaseTransformer(ABC):
    """
    Abstract base class for all data transformers.
    
    Each source system (Catalunya, Valencia, Galicia) must implement
    this interface to transform their raw data format into the
    universal NormalizedStation model.
    
    This follows the Strategy Pattern, allowing the system to select
    the appropriate transformation algorithm at runtime based on
    the source_system field.
    
    Attributes:
        source_system: Identifier for the data source (catalunya, valencia, galicia).
    """
    
    def __init__(self, source_system: str) -> None:
        """
        Initialize the transformer.
        
        Args:
            source_system: Source identifier (catalunya, valencia, galicia).
        """
        self.source_system = source_system.lower()
        self.rejected_items: list[dict[str, object]] = []

    def reset_rejections(self) -> None:
        """Reset collected rejected items before each transform call."""
        self.rejected_items = []

    def record_rejection(
        self,
        reason: str,
        raw_fragment: dict[str, object] | str | None,
    ) -> None:
        """Collect a rejected raw fragment with a machine-readable reason."""
        self.rejected_items.append(
            {
                "reason": reason,
                "raw_fragment": raw_fragment,
            }
        )

    def _validate_station(self, station: NormalizedStation) -> tuple[bool, str | None]:
        """
        Apply all validation rules to a station before accepting it.

        Validates:
        - Email format (simple regex)
        - Province is valid Spanish province
        - Coordinates are within province bounds
        - Contact information minimum requirements
        - Postal code matches province

        Args:
            station: NormalizedStation to validate

        Returns:
            Tuple of (is_valid: bool, reason: str | None)
            If is_valid is False, reason contains the rejection reason
        """
        # Validate email if present
        if station.email and not ITVValidationRules.validate_email_simple(station.email):
            return False, "invalid_email_format"

        # Validate province if present
        if station.province and not ITVValidationRules.validate_province_spain(station.province):
            return False, "invalid_province"

        # Validate coordinates by province
        if station.latitude and station.longitude and station.province:
            if not ITVValidationRules.validate_coordinates_by_province(
                station.latitude,
                station.longitude,
                station.province,
            ):
                return False, "coordinates_outside_province_bounds"

        # Validate postal code matches province
        if station.postal_code and station.province:
            if not ITVValidationRules.validate_postal_code_by_province(
                station.postal_code,
                station.province,
            ):
                return False, "postal_code_mismatch_province"

        # Validate minimum contact and location requirements
        if not ITVValidationRules.validate_contact_minimum(
            station.phone,
            station.email,
            station.address,
            station.city,
            station.province,
            station.postal_code,
        ):
            return False, "insufficient_contact_or_location"

        return True, None
    
    @abstractmethod
    def transform(self, raw_payload: Any) -> list[NormalizedStation]:
        """
        Transform raw data from source to normalized format.
        
        This is the main method that each transformer must implement.
        It receives the raw payload (XML string, JSON dict, CSV string, etc.)
        and returns a list of validated NormalizedStation objects.
        
        Args:
            raw_payload: Raw data in source-specific format.
                - Catalunya: XML string
                - Valencia: JSON dict or string
                - Galicia: CSV string
                
        Returns:
            List of NormalizedStation objects. Empty list if no valid stations.
            
        Raises:
            ValueError: If data cannot be parsed or is severely malformed.
            Exception: For other transformation errors (logged but not re-raised).
        """
        pass

    def _as_optional_str(self, value: object) -> str | None:
        """Normalize arbitrary values to a trimmed string or ``None``."""
        if value is None:
            return None

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        normalized = str(value).strip()
        return normalized or None
    
    def _generate_station_id(self, raw_id: str) -> str:
        """
        Generate unique station_id with source prefix.
        
        Creates a standardized station ID by combining the source prefix
        with the original ID from the source system.
        
        Args:
            raw_id: Original station ID from source system.
            
        Returns:
            Standardized station ID (e.g., CAT_BCN001, VAL_042, GAL_LU123).
            
        Examples:
            >>> transformer = CatalunyaTransformer()
            >>> transformer._generate_station_id("BCN-001")
            'CAT_BCN-001'
        """
        # Get first 3 letters of source in uppercase
        prefix = self.source_system[:3].upper()
        
        # Clean raw_id (remove extra whitespace)
        clean_id = str(raw_id).strip()
        
        return f"{prefix}_{clean_id}"
    
    def _parse_float(self, value: Any) -> float | None:
        """
        Safely parse float value from string or number.
        
        Handles various formats including comma decimal separators
        (common in Spanish data sources).
        
        Args:
            value: Value to parse (string, int, float, or None).
            
        Returns:
            Float value or None if parsing fails.
            
        Examples:
            >>> transformer._parse_float("41,3851")
            41.3851
            >>> transformer._parse_float("2.1734")
            2.1734
            >>> transformer._parse_float(None)
            None
        """
        if value is None or value == "":
            return None
        
        try:
            # Handle string values
            if isinstance(value, str):
                # Replace comma with period (Spanish number format)
                value = value.replace(",", ".").strip()
            
            return float(value)
        except (ValueError, AttributeError, TypeError):
            return None
    
    def _clean_phone(self, phone: str | None) -> str | None:
        """
        Clean and normalize phone number.
        
        Args:
            phone: Raw phone number string.
            
        Returns:
            Cleaned phone number or None.
        """
        if not phone:
            return None
        
        # Remove common separators and whitespace
        cleaned = phone.replace(" ", "").replace("-", "").replace(".", "")
        
        # Add +34 prefix if missing (Spanish numbers)
        if cleaned and not cleaned.startswith("+"):
            if cleaned.startswith("34"):
                cleaned = f"+{cleaned}"
            elif len(cleaned) == 9:  # Spanish mobile/landline without prefix
                cleaned = f"+34{cleaned}"
        
        return cleaned if cleaned else None
    
    def _clean_postal_code(self, postal_code: str | None) -> str | None:
        """
        Clean and validate Spanish postal code.
        
        Args:
            postal_code: Raw postal code string.
            
        Returns:
            5-digit postal code or None if invalid.
        """
        if not postal_code:
            return None
        
        # Extract only digits
        digits = "".join(filter(str.isdigit, str(postal_code)))
        
        # Spanish postal codes are exactly 5 digits
        if len(digits) == 5:
            return digits
        
        return None

    def _check_duplicate_within_message(
        self,
        stations: list[NormalizedStation],
    ) -> list[NormalizedStation]:
        """
        Filter out duplicate stations within the same message.

        Tracks station IDs and name+city combinations.
        If a duplicate is found, records rejection and removes it from list.

        Args:
            stations: List of NormalizedStation objects to check

        Returns:
            List of stations with duplicates removed
        """
        seen_ids: set[str] = set()
        seen_name_city: set[tuple[str, str]] = set()
        filtered_stations: list[NormalizedStation] = []

        for station in stations:
            station_id = station.station_id.upper()
            name_city_key = (station.name.upper(), (station.city or "").upper())

            # Check for duplicate ID
            if station_id in seen_ids:
                self.record_rejection(
                    reason="duplicate_id_within_message",
                    raw_fragment={
                        "station_id": station.station_id,
                        "name": station.name,
                        "city": station.city,
                    },
                )
                continue

            # Check for duplicate name+city combination (functional duplicate)
            if name_city_key in seen_name_city:
                self.record_rejection(
                    reason="duplicate_name_city_within_message",
                    raw_fragment={
                        "station_id": station.station_id,
                        "name": station.name,
                        "city": station.city,
                    },
                )
                continue

            seen_ids.add(station_id)
            seen_name_city.add(name_city_key)
            filtered_stations.append(station)

        return filtered_stations

    def _check_duplicate_contact_fields(
        self,
        stations: list[NormalizedStation],
    ) -> list[NormalizedStation]:
        """
        Filter out duplicate contact information within the same message.

        Detects stations with duplicate phone or email addresses.
        If duplicates found, keep first, record rejection for others.

        Args:
            stations: List of NormalizedStation objects to check

        Returns:
            List of stations with duplicate contacts removed
        """
        seen_phones: set[str] = set()
        seen_emails: set[str] = set()
        filtered_stations: list[NormalizedStation] = []

        for station in stations:
            should_keep = True

            # Check for duplicate phone
            if station.phone:
                phone_normalized = station.phone.upper()
                if phone_normalized in seen_phones:
                    self.record_rejection(
                        reason="duplicate_phone_in_message",
                        raw_fragment={
                            "station_id": station.station_id,
                            "phone": station.phone,
                        },
                    )
                    should_keep = False
                else:
                    seen_phones.add(phone_normalized)

            # Check for duplicate email
            if station.email and should_keep:
                email_normalized = station.email.lower()
                if email_normalized in seen_emails:
                    self.record_rejection(
                        reason="duplicate_email_in_message",
                        raw_fragment={
                            "station_id": station.station_id,
                            "email": station.email,
                        },
                    )
                    should_keep = False
                else:
                    seen_emails.add(email_normalized)

            if should_keep:
                filtered_stations.append(station)

        return filtered_stations
