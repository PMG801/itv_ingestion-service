"""Validation rules for ITV stations domain."""

import re
from typing import Optional


# Official Spanish provinces (50 total)
SPANISH_PROVINCES = {
    "ÁLAVA", "ALBACETE", "ALICANTE", "ALMERÍA", "ÁVILA",
    "BADAJOZ", "BARCELONA", "BURGOS", "CÁCERES", "CÁDIZ",
    "CANTABRIA", "CASTELLÓN", "CEUTA", "CIUDAD REAL", "CÓRDOBA",
    "CUENCA", "GIRONA", "GRANADA", "GUADALAJARA", "GUIPÚZCOA",
    "HUELVA", "HUESCA", "JAÉN", "LA CORUÑA", "LA RIOJA",
    "LAS PALMAS", "LEÓN", "LLEIDA", "LUGO", "MADRID",
    "MÁLAGA", "MELILLA", "MURCIA", "NAVARRA", "OURENSE",
    "PALENCIA", "PALMA", "PONTEVEDRA", "SALAMANCA", "SEGOVIA",
    "SEVILLA", "SORIA", "TARRAGONA", "TERUEL", "TOLEDO",
    "VALENCIA", "VALLADOLID", "VIZCAYA", "ZAMORA", "ZARAGOZA",
}

# Approximate geographic bounds by province (expanded margins to allow realistic variation)
# Ranges are intentionally generous to avoid false rejections while still validating plausibility
PROVINCE_COORDS_RANGE = {
    # Northeastern (Catalunya)
    "BARCELONA": {"lat": (40.9, 42.4), "lon": (1.2, 3.0)},
    "GIRONA": {"lat": (41.7, 42.5), "lon": (2.0, 3.4)},
    "LLEIDA": {"lat": (41.2, 43.1), "lon": (0.1, 2.0)},
    "TARRAGONA": {"lat": (40.7, 41.7), "lon": (0.4, 1.7)},
    
    # Eastern (Valencia & Murcia)
    "VALENCIA": {"lat": (38.5, 41.0), "lon": (-1.7, 0.2)},
    "CASTELLÓN": {"lat": (39.6, 41.0), "lon": (-1.2, 0.7)},
    "ALICANTE": {"lat": (37.5, 39.2), "lon": (-1.9, -0.2)},
    "MURCIA": {"lat": (37.1, 38.7), "lon": (-2.5, -0.7)},
    
    # Northeastern (Basque Country & Navarra)
    "VIZCAYA": {"lat": (42.6, 43.5), "lon": (-3.7, -2.5)},
    "GUIPÚZCOA": {"lat": (42.9, 43.5), "lon": (-2.8, -1.4)},
    "ÁLAVA": {"lat": (42.2, 43.3), "lon": (-3.8, -2.3)},
    "NAVARRA": {"lat": (42.0, 43.2), "lon": (-3.3, -1.0)},
    
    # Northern (Rioja & Cantabria)
    "LA RIOJA": {"lat": (41.6, 42.8), "lon": (-3.4, -1.8)},
    "CANTABRIA": {"lat": (42.8, 43.6), "lon": (-4.0, -3.0)},
    
    # Northwestern (Galicia)
    "A CORUÑA": {"lat": (42.0, 43.2), "lon": (-9.5, -7.6)},
    "LUGO": {"lat": (42.2, 43.4), "lon": (-9.0, -7.3)},
    "OURENSE": {"lat": (41.6, 42.8), "lon": (-8.9, -7.1)},
    "PONTEVEDRA": {"lat": (41.6, 42.8), "lon": (-9.1, -7.8)},
    
    # Northern central (Asturias & León)
    "LEÓN": {"lat": (41.6, 43.4), "lon": (-6.9, -4.8)},
    "PALENCIA": {"lat": (41.4, 42.7), "lon": (-5.9, -3.9)},
    "VALLADOLID": {"lat": (40.8, 42.5), "lon": (-5.4, -3.5)},
    "BURGOS": {"lat": (40.6, 43.2), "lon": (-4.4, -2.3)},
    "SORIA": {"lat": (40.6, 42.5), "lon": (-4.1, -2.0)},
    
    # Central Plateau (Castilla-La Mancha & Castilla y León)
    "MADRID": {"lat": (39.8, 41.4), "lon": (-4.5, -2.5)},
    "SEGOVIA": {"lat": (40.3, 41.7), "lon": (-4.8, -3.2)},
    "ÁVILA": {"lat": (39.8, 41.5), "lon": (-6.2, -4.3)},
    "TOLEDO": {"lat": (39.0, 40.7), "lon": (-5.2, -3.0)},
    "CUENCA": {"lat": (39.6, 41.0), "lon": (-4.1, -1.8)},
    "GUADALAJARA": {"lat": (39.8, 41.5), "lon": (-4.6, -1.9)},
    "CIUDAD REAL": {"lat": (38.3, 40.0), "lon": (-5.3, -2.9)},
    "ALBACETE": {"lat": (38.1, 40.0), "lon": (-4.3, -0.8)},
    
    # Southern (Andalucía)
    "BADAJOZ": {"lat": (37.6, 40.0), "lon": (-7.9, -4.7)},
    "CÓRDOBA": {"lat": (37.2, 39.0), "lon": (-5.5, -3.2)},
    "SEVILLA": {"lat": (36.5, 38.5), "lon": (-7.2, -4.2)},
    "JAÉN": {"lat": (37.4, 39.0), "lon": (-4.8, -2.4)},
    "CÁDIZ": {"lat": (35.8, 37.3), "lon": (-6.7, -5.2)},
    "MÁLAGA": {"lat": (36.2, 37.6), "lon": (-5.3, -3.2)},
    "GRANADA": {"lat": (36.5, 38.1), "lon": (-4.8, -2.3)},
    "ALMERÍA": {"lat": (36.2, 37.7), "lon": (-3.8, -1.5)},
    
    # Autonomous cities in North Africa
    "CEUTA": {"lat": (35.8, 36.1), "lon": (-5.5, -5.2)},
    "MELILLA": {"lat": (35.2, 35.5), "lon": (-3.4, -3.1)},
    
    # Balearic Islands
    "PALMA": {"lat": (39.2, 39.8), "lon": (2.4, 3.2)},
    
    # Canary Islands
    "LAS PALMAS": {"lat": (27.5, 28.5), "lon": (-16.1, -15.0)},
}

# Postal code ranges by province (first 2 digits)
PROVINCE_POSTAL_CODES = {
    "ÁLAVA": "01",
    "ALBACETE": "02",
    "ALICANTE": "03",
    "ALMERÍA": "04",
    "ÁVILA": "05",
    "BADAJOZ": "06",
    "BARCELONA": "08",
    "BURGOS": "09",
    "CÁCERES": "10",
    "CÁDIZ": "11",
    "CANTABRIA": "39",
    "CASTELLÓN": "12",
    "CEUTA": "51",
    "CIUDAD REAL": "13",
    "CÓRDOBA": "14",
    "CUENCA": "16",
    "GIRONA": "17",
    "GRANADA": "18",
    "GUADALAJARA": "19",
    "GUIPÚZCOA": "20",
    "HUELVA": "21",
    "HUESCA": "22",
    "JAÉN": "23",
    "LA CORUÑA": "15",
    "LA RIOJA": "26",
    "LAS PALMAS": "35",
    "LEÓN": "24",
    "LLEIDA": "25",
    "LUGO": "27",
    "MADRID": "28",
    "MÁLAGA": "29",
    "MELILLA": "52",
    "MURCIA": "30",
    "NAVARRA": "31",
    "OURENSE": "32",
    "PALENCIA": "34",
    "PALMA": "07",
    "PONTEVEDRA": "36",
    "SALAMANCA": "37",
    "SEGOVIA": "40",
    "SEVILLA": "41",
    "SORIA": "42",
    "TARRAGONA": "43",
    "TERUEL": "44",
    "TOLEDO": "45",
    "VALENCIA": "46",
    "VALLADOLID": "47",
    "VIZCAYA": "48",
    "ZAMORA": "49",
    "ZARAGOZA": "50",
}


class ITVValidationRules:
    """Validation rules specific to ITV stations."""

    # Spain geographic bounds (approximate)
    SPAIN_LAT_MIN = 36.0
    SPAIN_LAT_MAX = 43.8
    SPAIN_LON_MIN = -9.3
    SPAIN_LON_MAX = 4.3

    @classmethod
    def validate_coordinates(cls, latitude: float | None, longitude: float | None) -> bool:
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
            cls.SPAIN_LAT_MIN <= latitude <= cls.SPAIN_LAT_MAX
            and cls.SPAIN_LON_MIN <= longitude <= cls.SPAIN_LON_MAX
        )

    @classmethod
    def validate_email_simple(cls, email: Optional[str]) -> bool:
        """
        Validate email with simple regex pattern (RFC 5322 basic).

        Args:
            email: Email address to validate

        Returns:
            bool: True if email matches simple pattern user@domain.com
        """
        if not email or not isinstance(email, str):
            return False

        # Simple pattern: word characters @ word characters . word characters
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return bool(re.match(pattern, email.strip()))

    @classmethod
    def validate_province_spain(cls, province: Optional[str]) -> bool:
        """
        Validate if province is in official Spanish provinces list.

        Args:
            province: Province name to validate

        Returns:
            bool: True if province is a valid Spanish province
        """
        if not province or not isinstance(province, str):
            return False

        return province.strip().upper() in SPANISH_PROVINCES

    @classmethod
    def validate_coordinates_by_province(
        cls,
        latitude: Optional[float],
        longitude: Optional[float],
        province: Optional[str],
    ) -> bool:
        """
        Validate coordinates are within expected bounds for given province.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            province: Province name

        Returns:
            bool: True if coordinates fall within province bounds
        """
        if latitude is None or longitude is None or not province:
            return False

        province_upper = province.strip().upper()

        if province_upper not in PROVINCE_COORDS_RANGE:
            # If province not in our dataset, fall back to Spain bounds validation
            return cls.validate_coordinates(latitude, longitude)

        bounds = PROVINCE_COORDS_RANGE[province_upper]
        lat_min, lat_max = bounds["lat"]
        lon_min, lon_max = bounds["lon"]

        return (
            lat_min <= latitude <= lat_max
            and lon_min <= longitude <= lon_max
        )

    @classmethod
    def validate_postal_code_by_province(
        cls,
        postal_code: Optional[str],
        province: Optional[str],
    ) -> bool:
        """
        Validate postal code matches province prefix (first 2 digits).

        Args:
            postal_code: 5-digit postal code
            province: Province name

        Returns:
            bool: True if postal code prefix matches province
        """
        if not postal_code or not province:
            return False

        if not isinstance(postal_code, str) or len(postal_code) != 5:
            return False

        province_upper = province.strip().upper()

        if province_upper not in PROVINCE_POSTAL_CODES:
            # If province not in our dataset, skip validation (allow it)
            return True

        expected_prefix = PROVINCE_POSTAL_CODES[province_upper]
        return postal_code.startswith(expected_prefix)

    @classmethod
    def validate_contact_minimum(
        cls,
        phone: Optional[str],
        email: Optional[str],
        address: Optional[str],
        city: Optional[str],
        province: Optional[str],
        postal_code: Optional[str],
    ) -> bool:
        """
        Validate minimum contact and location requirements.

        Requirements:
        - At least ONE of: phone or email (preferably non-empty)
        - ALL location fields required: address, city, province, postal_code

        Args:
            phone: Phone number
            email: Email address
            address: Street address
            city: City name
            province: Province name
            postal_code: Postal code

        Returns:
            bool: True if minimum contact and location requirements met
        """
        # At least ONE contact method (phone or email)
        has_phone = bool(phone and isinstance(phone, str) and phone.strip())
        has_email = bool(email and isinstance(email, str) and email.strip())
        has_contact = has_phone or has_email

        # ALL location fields must be present
        has_address = bool(address and isinstance(address, str) and address.strip())
        has_city = bool(city and isinstance(city, str) and city.strip())
        has_province = bool(province and isinstance(province, str) and province.strip())
        has_postal_code = bool(postal_code and isinstance(postal_code, str) and postal_code.strip())

        has_location = has_address and has_city and has_province and has_postal_code

        return has_contact and has_location
