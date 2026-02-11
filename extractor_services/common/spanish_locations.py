"""Datos oficiales de provincias de España con validación por código postal.

Incluye las provincias de Cataluña, Comunidad Valenciana y Galicia.
También incluye rangos de coordenadas geográficas válidas por provincia.
"""

import logging
from typing import Dict, Set, Tuple, List

logger = logging.getLogger(__name__)

# Rangos de códigos postales por provincia
# Los códigos postales en España siguen un patrón: los 2 primeros dígitos identifican la provincia
RANGOS_CODIGOS_POSTALES: Dict[str, List[Tuple[int, int]]] = {
    # CATALUÑA
    "Barcelona": [(8000, 8999)],  # 08xxx
    "Girona": [(17000, 17999)],   # 17xxx
    "Lleida": [(25000, 25999)],   # 25xxx
    "Tarragona": [(43000, 43999)], # 43xxx
    
    # COMUNIDAD VALENCIANA
    "Valencia": [(46000, 46999)],  # 46xxx
    "Alicante": [(3000, 3999)],    # 03xxx
    "Castellón": [(12000, 12999)], # 12xxx
    
    # GALICIA
    "A Coruña": [(15000, 15999)],  # 15xxx
    "Lugo": [(27000, 27999)],      # 27xxx
    "Ourense": [(32000, 32999)],   # 32xxx
    "Pontevedra": [(36000, 36999)], # 36xxx
}

# Lista de todas las provincias válidas
PROVINCIAS_VALIDAS: Set[str] = set(RANGOS_CODIGOS_POSTALES.keys())

# Mapeo de variantes de nombres de provincias
PROVINCIA_ALIASES: Dict[str, str] = {
    # Cataluña
    "barcelona": "Barcelona",
    "girona": "Girona",
    "lleida": "Lleida",
    "lérida": "Lleida",
    "tarragona": "Tarragona",
    
    # Comunidad Valenciana
    "valencia": "Valencia",
    "valència": "València",
    "alicante": "Alicante",
    "alacant": "Alicante",
    "castellón": "Castellón",
    "castelló": "Castellón",
    "castellon": "Castellón",
    "castello": "Castellón",
    "castellón de la plana": "Castellón",
    "castelló de la plana": "Castellón",
    
    # Galicia
    "a coruña": "A Coruña",
    "la coruña": "A Coruña",
    "coruña": "A Coruña",
    "lugo": "Lugo",
    "ourense": "Ourense",
    "orense": "Ourense",
    "pontevedra": "Pontevedra"
}

# Rangos de coordenadas geográficas por provincia
# Formato: (lat_min, lat_max, lon_min, lon_max)
RANGOS_COORDENADAS_PROVINCIAS: Dict[str, Tuple[float, float, float, float]] = {
    # CATALUÑA
    "Barcelona": (41.2, 42.0, 1.5, 3.0),
    "Girona": (41.7, 42.5, 2.0, 3.4),
    "Lleida": (41.3, 42.9, 0.1, 2.0),
    "Tarragona": (40.5, 41.5, 0.2, 1.8),
    
    # COMUNIDAD VALENCIANA
    "Valencia": (38.5, 40.2, -1.5, 0.6),
    "Alicante": (37.5, 38.6, -1.6, 0.3),
    "Castellón": (39.9, 40.9, -1.2, 0.6),
    
    # GALICIA
    "A Coruña": (42.5, 43.8, -9.3, -7.5),
    "Lugo": (42.3, 43.8, -7.9, -6.7),
    "Ourense": (41.8, 43.0, -8.5, -6.8),
    "Pontevedra": (42.0, 42.8, -9.0, -8.0),
}

# Rango general de coordenadas de España (incluyendo península y Baleares)
# Excluye Canarias que están muy al sur
RANGO_COORDENADAS_ESPANA: Tuple[float, float, float, float] = (
    36.0,   # Latitud mínima (sur de Andalucía)
    43.8,   # Latitud máxima (norte de Galicia)
    -9.5,   # Longitud mínima (oeste de Galicia)
    4.5     # Longitud máxima (este de Cataluña y Baleares)
)


def normalizar_provincia(provincia: str) -> str:
    """Normaliza el nombre de la provincia y devuelve el nombre oficial.
    
    Args:
        provincia: Nombre de la provincia (puede tener variantes)
        
    Returns:
        Nombre oficial de la provincia o el original si no se encuentra
    """
    if not provincia:
        return provincia
    
    provincia_lower = provincia.strip().lower()
    return PROVINCIA_ALIASES.get(provincia_lower, provincia.strip())


def obtener_provincia_por_codigo_postal(codigo_postal: str) -> str:
    """Obtiene el nombre de la provincia basándose en el código postal.
    
    Args:
        codigo_postal: Código postal (5 dígitos)
        
    Returns:
        Nombre oficial de la provincia o cadena vacía si no se encuentra
    """
    if not codigo_postal or len(codigo_postal) < 2:
        return ""
    
    try:
        # Extraer los 2 primeros dígitos
        codigo_num = int(codigo_postal[:5]) if len(codigo_postal) >= 5 else int(codigo_postal[:2]) * 1000
        
        for provincia, rangos in RANGOS_CODIGOS_POSTALES.items():
            for rango_min, rango_max in rangos:
                if rango_min <= codigo_num <= rango_max:
                    return provincia
    except (ValueError, TypeError):
        logger.warning(f"Código postal inválido: {codigo_postal}")
    
    return ""


def validar_codigo_postal(codigo_postal: str, provincia: str) -> bool:
    """Valida que un código postal pertenezca a una provincia.
    
    Args:
        codigo_postal: Código postal a validar (5 dígitos)
        provincia: Nombre de la provincia
        
    Returns:
        True si el código postal es válido para la provincia
    """
    if not codigo_postal or not provincia:
        return False
    
    provincia_normalizada = normalizar_provincia(provincia)
    if provincia_normalizada not in RANGOS_CODIGOS_POSTALES:
        return False
    
    try:
        # Convertir código postal a número
        if len(codigo_postal) < 5:
            codigo_postal = codigo_postal.zfill(5)
        
        codigo_num = int(codigo_postal)
        
        # Verificar si está en algún rango de la provincia
        rangos = RANGOS_CODIGOS_POSTALES[provincia_normalizada]
        for rango_min, rango_max in rangos:
            if rango_min <= codigo_num <= rango_max:
                return True
                
        return False
        
    except (ValueError, TypeError):
        return False


def obtener_rangos_codigo_postal_provincia(provincia: str) -> List[Tuple[int, int]]:
    """Obtiene los rangos de códigos postales válidos para una provincia.
    
    Args:
        provincia: Nombre de la provincia
        
    Returns:
        Lista de tuplas con (codigo_min, codigo_max)
    """
    provincia_normalizada = normalizar_provincia(provincia)
    return RANGOS_CODIGOS_POSTALES.get(provincia_normalizada, [])


def obtener_rango_coordenadas_provincia(provincia: str) -> Tuple[float, float, float, float]:
    """Obtiene el rango de coordenadas válidas para una provincia.
    
    Args:
        provincia: Nombre de la provincia
        
    Returns:
        Tuple con (lat_min, lat_max, lon_min, lon_max) o rango de España si no existe
    """
    provincia_normalizada = normalizar_provincia(provincia)
    return RANGOS_COORDENADAS_PROVINCIAS.get(provincia_normalizada, RANGO_COORDENADAS_ESPANA)
