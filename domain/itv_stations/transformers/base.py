"""
Base transformer interface following Strategy Pattern.

This module defines the abstract base class that all source-specific
transformers must implement to ensure consistent data transformation.
"""

from abc import ABC, abstractmethod
from typing import Any

from domain.itv_stations.schemas import NormalizedStation


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
    
    def __init__(self, source_system: str):
        """
        Initialize the transformer.
        
        Args:
            source_system: Source identifier (catalunya, valencia, galicia).
        """
        self.source_system = source_system.lower()
    
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
