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
from typing import Literal, Optional, Any
from datetime import datetime, timezone
from faker import Faker

fake = Faker("es_ES")  # Usar locale Español


class SyntheticDataGenerator:
    """Generador de datos sintéticos para estaciones ITV."""

    SOURCES = {
        "catalunya": {"prefix": "CAT", "region": "Cataluña"},
        "valencia": {"prefix": "VAL", "region": "Valencia"},
        "galicia": {"prefix": "GAL", "region": "Galicia"},
    }

    # Coordenadas por región (aproximadas)
    REGION_COORDS = {
        "catalana": {"lat_range": (41.0, 42.9), "lon_range": (0.1, 3.3)},
        "valencia": {"lat_range": (38.6, 40.8), "lon_range": (-1.5, -0.1)},
        "galicia": {"lat_range": (42.1, 43.8), "lon_range": (-9.3, -7.0)},
    }

    STATION_TYPES = ["Fija", "Móvil", "Portátil"]

    @classmethod
    def generate_stations(
        cls,
        source: Literal["catalunya", "valencia", "galicia"],
        count: int = 10,
        error_rate: float = 0.0,
        include_errors: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Genera un lote de estaciones ITV sintéticas.

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
            Lista de dicts con datos de estaciones normalizadas
        """
        if source not in cls.SOURCES:
            raise ValueError(f"Fuente inválida: {source}. Usar: {list(cls.SOURCES.keys())}")

        include_errors = include_errors or []
        stations = []

        for i in range(count):
            station = cls._generate_single_station(source, i + 1, error_rate, include_errors)
            stations.append(station)

        return stations  # type: ignore[return-value]

    @classmethod
    def _generate_single_station(
        cls,
        source: Literal["catalunya", "valencia", "galicia"],
        index: int,
        error_rate: float,
        include_errors: list[str],
    ) -> dict[str, Any]:
        """Genera una estación ITV individual."""
        import random

        source_info = cls.SOURCES[source]
        prefix = source_info["prefix"]
        region = source_info["region"]

        # ID único por fuente
        station_id = f"{prefix}-{index:06d}"

        # Nombre realista
        city = fake.city()
        name = f"ITV {city} - {random.choice(cls.STATION_TYPES)}"

        # Coordenadas (dentro de la región por defecto)
        region_key = source.lower() if source == "catalunya" else source
        coords = cls.REGION_COORDS.get(region_key, {"lat_range": (40.0, 43.0), "lon_range": (-3.0, 4.0)})

        lat_range, lon_range = coords["lat_range"], coords["lon_range"]
        latitude = round(random.uniform(*lat_range), 4)
        longitude = round(random.uniform(*lon_range), 4)

        # Datos de contacto
        phone = fake.phone_number()[:15]
        email = fake.email()
        address = fake.street_address()
        postal_code = f"{random.randint(1, 99):02d}{random.randint(1, 99):02d}{random.randint(0, 9)}"

        # Inyectar errores probabilísticamente
        should_error = random.random() < error_rate
        error_type = random.choice(include_errors) if error_rate > 0 and should_error else None

        # Aplicar errores
        if error_type == "invalid_coordinates":
            # Coordenadas fuera de España
            latitude = random.uniform(50.0, 60.0)  # Fuera de rango España (36-43.8)
            longitude = random.uniform(-5.0, -2.0)
        elif error_type == "missing_field":
            # Hacer falta un campo obligatorio
            address = None
        elif error_type == "duplicate":
            # Duplicar ID (será detectado como duplicado)
            station_id = f"{prefix}-000001"
        elif error_type == "malformed_phone":
            # Teléfono inválido
            phone = "INVALID-PHONE"

        station_data = {
            "station_id": station_id,
            "name": name,
            "source_system": source,
            "raw_id": station_id,  # El ID original antes de normalización
            "address": address,
            "city": city.upper(),  # Normalizar a mayúsculas
            "province": region.upper(),
            "postal_code": postal_code,
            "latitude": latitude,
            "longitude": longitude,
            "phone": phone,
            "email": email,
            "normalized_at": datetime.now(timezone.utc).isoformat(),
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
        stations = cls.generate_stations(source, count, error_rate)

        if format_type == "json":
            return json.dumps({"stations": stations}, indent=2)

        elif format_type == "xml":
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<itv_stations source="{source}">
"""
            for station in stations:
                xml += f"""  <station>
    <id>{station['station_id']}</id>
    <name>{station['name']}</name>
    <address>{station['address']}</address>
    <city>{station['city']}</city>
    <province>{station['province']}</province>
    <postal_code>{station['postal_code']}</postal_code>
    <latitude>{station['latitude']}</latitude>
    <longitude>{station['longitude']}</longitude>
    <phone>{station['phone']}</phone>
    <email>{station['email']}</email>
  </station>
"""
            xml += "</itv_stations>"
            return xml

        elif format_type == "csv":
            import csv
            from io import StringIO

            output = StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "station_id",
                    "name",
                    "address",
                    "city",
                    "province",
                    "postal_code",
                    "latitude",
                    "longitude",
                    "phone",
                    "email",
                ],
            )
            writer.writeheader()
            writer.writerows(stations)
            return output.getvalue()

        else:
            raise ValueError(f"Formato no soportado: {format_type}")


# Export para uso directo
__all__ = ["SyntheticDataGenerator"]
