"""Validation rules for ITV stations domain."""

from typing import Tuple


class ITVValidationRules:
    """Validation rules specific to ITV stations."""
    
    # Spain geographic bounds (approximate)
    SPAIN_LAT_MIN = 36.0
    SPAIN_LAT_MAX = 43.8
    SPAIN_LON_MIN = -9.3
    SPAIN_LON_MAX = 4.3
    
    @classmethod
    def validate_coordinates(cls, latitude: float, longitude: float) -> bool:
        """
        Validate if coordinates are within Spain boundaries.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            bool: True if coordinates are valid for Spain
        """
        if latitude is None or longitude is None:
            return False
            
        return (
            cls.SPAIN_LAT_MIN <= latitude <= cls.SPAIN_LAT_MAX and
            cls.SPAIN_LON_MIN <= longitude <= cls.SPAIN_LON_MAX
        )
