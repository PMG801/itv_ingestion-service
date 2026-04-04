"""
Synthetic Data Generator para pruebas de benchmarking.

Genera estaciones ITV realistas usando Faker, respetando convenciones de nombre
por fuente y permitiendo inyección controlada de errores.

Utilizado para:
1. Pruebas de carga (load testing) sin dependencias externas
2. Benchmarking de latencia por fuente
3. Validación de rejection logic
"""

import json
import random
from typing import Literal, Optional, Any
from datetime import datetime, timezone
from faker import Faker

from domain.itv_stations.rules import PROVINCE_COORDS_RANGE, PROVINCE_POSTAL_CODES

fake = Faker("es_ES")  # Usar locale Español


class SyntheticDataGenerator:
    """Generador de datos sintéticos para estaciones ITV."""

    STATION_TYPES = (
        "Fija",
        "Móvil",
        "Industrial",
        "Turismos",
        "Mixta",
    )

    SOURCES = {
        "catalunya": {"prefix": "CAT", "region": "Catalonia"},
        "valencia": {"prefix": "VAL", "region": "Valencia"},
        "galicia": {"prefix": "GAL", "region": "Galicia"},
    }

    # Provincias por región (nombres válidos según SPANISH_PROVINCES en rules.py)
    REGION_PROVINCES = {
        "catalunya": ["BARCELONA", "GIRONA", "LLEIDA", "TARRAGONA"],
        "valencia": ["CASTELLÓN", "VALENCIA", "ALICANTE"],
        "galicia": ["LA CORUÑA", "LUGO", "OURENSE", "PONTEVEDRA"],
    }

    # Coordenadas por región (aproximadas)
    REGION_COORDS = {
        "catalunya": {"lat_range": (41.0, 42.9), "lon_range": (0.1, 3.3)},
        "valencia": {"lat_range": (38.6, 40.8), "lon_range": (-1.5, -0.1)},
        "galicia": {"lat_range": (42.1, 43.8), "lon_range": (-9.3, -7.0)},
    }

    PROVINCE_CITIES = {
        "catalunya": {
            "BARCELONA": ["Barcelona", "L'Hospitalet de Llobregat", "Badalona", "Terrassa"],
            "GIRONA": ["Girona", "Figueres", "Blanes", "Olot"],
            "LLEIDA": ["Lleida", "Tàrrega", "Balaguer", "Mollerussa"],
            "TARRAGONA": ["Tarragona", "Reus", "Valls", "El Vendrell"],
        },
        "valencia": {
            "VALENCIA": ["Valencia", "Torrent", "Gandia", "Sagunto"],
            "CASTELLÓN": ["Castellón de la Plana", "Vila-real", "Borriana", "Vinaròs"],
            "ALICANTE": ["Alicante", "Elche", "Torrevieja", "Elda"],
        },
        "galicia": {
            "LA CORUÑA": ["A Coruña", "Santiago de Compostela", "Ferrol", "Narón"],
            "LUGO": ["Lugo", "Monforte de Lemos", "Viveiro", "Sarria"],
            "OURENSE": ["Ourense", "Verín", "O Carballiño", "Barbadás"],
            "PONTEVEDRA": ["Pontevedra", "Vigo", "Vilagarcía de Arousa", "Lalín"],
        },
    }


    @classmethod
    def _get_postal_code_prefix(cls, province: str) -> str:
        """
        Obtiene el prefijo postal correcto (primeros 2 dígitos) para una provincia.
        
        Basado en PROVINCE_POSTAL_CODES de domain.itv_stations.rules.
        """
        return PROVINCE_POSTAL_CODES.get(province.upper(), "28")  # Default Madrid

    @classmethod
    def _get_city_for_province(cls, source: str, province: str) -> str:
        province_upper = province.upper()
        source_cities = cls.PROVINCE_CITIES.get(source, {})
        if province_upper in source_cities:
            return random.choice(source_cities[province_upper])
        return fake.city()

    @classmethod
    def _get_coordinates_for_province(cls, source: str, province: str) -> tuple[float, float]:
        province_upper = province.upper()
        bounds = PROVINCE_COORDS_RANGE.get(province_upper)
        if bounds:
            return (
                round(random.uniform(*bounds["lat"]), 4),
                round(random.uniform(*bounds["lon"]), 4),
            )

        coords = cls.REGION_COORDS.get(source, {"lat_range": (40.0, 43.0), "lon_range": (-3.0, 4.0)})
        return (
            round(random.uniform(*coords["lat_range"]), 4),
            round(random.uniform(*coords["lon_range"]), 4),
        )

    @classmethod
    def generate_stations(
        cls,
        source: Literal["catalunya", "valencia", "galicia"],
        count: int = 10,
        error_rate: float = 0.0,
        include_errors: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Genera un lote de estaciones ITV sintéticas con formato específico por región.

        Args:
            source: Fuente ('catalunya', 'valencia', 'galicia')
            count: Número de estaciones a generar
            error_rate: Probabilidad (0.0-1.0) de introducir errores
            include_errors: Tipos específicos de errores a inyectar
                - 'invalid_coordinates': coordenadas fuera de España
                - 'missing_field': campos obligatorios faltantes
                - 'duplicate': IDs duplicados
                - 'malformed_phone': teléfono inválido

        Returns:
            Payload con estaciones en el formato esperado por cada transformador:
            - Catalunya: dict con clave "stations"
            - Valencia: dict con clave "estaciones"
            - Galicia: dict con clave "stations"
        """
        if source not in cls.SOURCES:
            raise ValueError(f"Fuente inválida: {source}. Usar: {list(cls.SOURCES.keys())}")

        include_errors = include_errors or []
        stations = []

        for i in range(count):
            station = cls._generate_single_station(source, i + 1, error_rate, include_errors)
            stations.append(station)

        # Envolver con la clave correcta según la fuente
        if source == "valencia":
            # Valencia espera "estaciones", no "stations"
            return {"estaciones": stations}
        else:
            # Catalunya y Galicia: usa "stations"
            return {"stations": stations}

    @classmethod
    def _generate_single_station(
        cls,
        source: Literal["catalunya", "valencia", "galicia"],
        index: int,
        error_rate: float,
        include_errors: list[str],
    ) -> dict[str, Any]:
        """
        Genera una estación ITV individual con formato específico por región.
        
        Los datos se generan en el formato que cada transformador espera:
        - Catalunya: campos catalanes (id, nom, adreca, ciutat, provincia, etc.)
        - Valencia: campos españoles/valencianos (codigo, nombre, direccion, poblacion, provincia, etc.)
        - Galicia: campos gallegos (id, nome, enderezo, concello, provincia, etc.)
        """
        source_info = cls.SOURCES[source]
        prefix = source_info["prefix"]
        
        # Seleccionar provincia válida para la región
        provinces = cls.REGION_PROVINCES.get(source, ["BARCELONA", "VALENCIA", "A CORUÑA"])
        province = random.choice(provinces)
        
        # ID único por fuente
        station_id = f"{prefix}-{index:06d}"

        # Nombre realista
        city = cls._get_city_for_province(source, province)
        name = f"ITV {city} - {random.choice(cls.STATION_TYPES)}"

        # Coordenadas según provincia para evitar rechazos por límites geográficos
        latitude, longitude = cls._get_coordinates_for_province(source, province)

        # Datos de contacto
        phone = fake.phone_number()[:15]
        email = fake.email()
        address = fake.street_address()
        
        # Generar postal code válido para la provincia
        # Primero 2 dígitos según provincia, luego 3 dígitos aleatorios
        postal_prefix = cls._get_postal_code_prefix(province)
        postal_code = f"{postal_prefix}{random.randint(0, 999):03d}"

        # Inyectar errores probabilísticamente
        should_error = random.random() < error_rate
        error_type = random.choice(include_errors) if error_rate > 0 and should_error else None

        # Aplicar errores
        if error_type == "invalid_coordinates":
            latitude = random.uniform(50.0, 60.0)  # Fuera de rango España
            longitude = random.uniform(-5.0, -2.0)
        elif error_type == "missing_field":
            address = None
        elif error_type == "duplicate":
            station_id = f"{prefix}-000001"
        elif error_type == "malformed_phone":
            phone = "INVALID-PHONE"

        # Generar datos en formato específico por región
        if source == "catalunya":
            # formato Catalán
            station_data = {
                "id": station_id,
                "nom": name,
                "adreca": address,
                "ciutat": city.upper(),
                "provincia": province,
                "codi_postal": postal_code,
                "latitud": latitude,
                "longitud": longitude,
                "telefon": phone,
                "email": email,
            }
        elif source == "valencia":
            # Formato Valenciano/Español
            station_data = {
                "codigo": station_id,
                "nombre": name,
                "direccion": address,
                "poblacion": city.upper(),
                "provincia": province,
                "codigo_postal": postal_code,
                "latitud": latitude,
                "longitud": longitude,
                "telefono": phone,
                "correo": email,
            }
        else:  # galicia
            # Formato Gallego
            station_data = {
                "id": station_id,
                "nome": name,
                "enderezo": address,
                "concello": city.upper(),
                "provincia": province,
                "cp": postal_code,
                "lat": latitude,
                "lon": longitude,
                "telefono": phone,
                "email": email,
            }

        return station_data

    @classmethod
    def generate_raw_payload(
        cls,
        source: Literal["catalunya", "valencia", "galicia"],
        count: int = 10,
        format_type: Literal["json", "xml", "csv"] = "json",
        error_rate: float = 0.0,
    ) -> str:
        """
        Genera un payload crudo (sin normalizar) en el formato especificado.

        Útil para probar transformadores.

        Args:
            source: Fuente de datos
            count: Número de estaciones
            format_type: Formato del payload ('json', 'xml', 'csv')
            error_rate: Tasa de error a inyectar

        Returns:
            Payload como string (JSON, XML o CSV)
        """
        payload = cls.generate_stations(source, count, error_rate)
        
        # Extraer la lista de estaciones
        if source == "valencia":
            stations = payload.get("estaciones", [])
        else:
            stations = payload.get("stations", [])

        if format_type == "json":
            return json.dumps(payload, indent=2)

        elif format_type == "xml":
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<itv_stations source="{source}">
"""
            for station in stations:
                if source == "catalunya":
                    xml += f"""  <station>
    <id>{station.get('id', '')}</id>
    <nom>{station.get('nom', '')}</nom>
    <adreca>{station.get('adreca', '')}</adreca>
    <ciutat>{station.get('ciutat', '')}</ciutat>
    <provincia>{station.get('provincia', '')}</provincia>
    <codi_postal>{station.get('codi_postal', '')}</codi_postal>
    <latitud>{station.get('latitud', '')}</latitud>
    <longitud>{station.get('longitud', '')}</longitud>
    <telefon>{station.get('telefon', '')}</telefon>
    <email>{station.get('email', '')}</email>
  </station>
"""
            xml += "</itv_stations>"
            return xml

        elif format_type == "csv":
            import csv
            from io import StringIO

            output = StringIO()
            if source == "catalunya":
                fieldnames = ["id", "nom", "adreca", "ciutat", "provincia", "codi_postal", "latitud", "longitud", "telefon", "email"]
            elif source == "valencia":
                fieldnames = ["codigo", "nombre", "direccion", "poblacion", "provincia", "codigo_postal", "latitud", "longitud", "telefono", "correo"]
            else:  # galicia
                fieldnames = ["id", "nome", "enderezo", "concello", "provincia", "cp", "lat", "lon", "telefono", "email"]
            
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(stations)
            return output.getvalue()

        else:
            raise ValueError(f"Formato no soportado: {format_type}")


# Export para uso directo
__all__ = ["SyntheticDataGenerator"]
