"""
Transformador de datos de Catalunya.
Convierte los datos crudos del XML al formato estandarizado EstacionExtraida.

NOTA: Esta versión NO interactúa con la base de datos. 
Solo transforma los datos para enviarlos a la API central.
"""
import re
import logging
from typing import Optional, Tuple

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import EstacionExtraida, TipoEstacion
from common.normalizers import (
    normalize_codigo_postal,
    normalize_estacion_name,
    is_valid_email
)
from common.spanish_locations import (
    PROVINCIAS_VALIDAS,
    normalizar_provincia as normalizar_provincia_base,
    validar_codigo_postal as validar_cp_provincia,
    obtener_rango_coordenadas_provincia
)

logger = logging.getLogger(__name__)


# ===== VALIDATORS =====

# Provincias de Catalunya con sus variantes de nombre (para el campo "serveis_territorials")
PROVINCIAS_CAT_VARIANTES = {
    "barcelona": "Barcelona",
    "girona": "Girona",
    "lleida": "Lleida",
    "tarragona": "Tarragona",
    # Variantes catalanas del campo serveis_territorials
    "serveis territorials a barcelona": "Barcelona",
    "serveis territorials a girona": "Girona",
    "serveis territorials a lleida": "Lleida",
    "serveis territorials a tarragona": "Tarragona",
    "serveis territorials de barcelona": "Barcelona",
    "serveis territorials de girona": "Girona",
    "serveis territorials de lleida": "Lleida",
    "serveis territorials de tarragona": "Tarragona",
}


def normalizar_provincia(provincia: str) -> Tuple[bool, Optional[str]]:
    """Normaliza y valida provincia catalana."""
    if not provincia:
        return False, None
    
    from unidecode import unidecode
    prov_norm = unidecode(provincia.strip().lower())
    
    # Primero intentar con las variantes locales de Catalunya
    if prov_norm in PROVINCIAS_CAT_VARIANTES:
        return True, PROVINCIAS_CAT_VARIANTES[prov_norm]
    
    # Buscar coincidencia parcial
    for key, value in PROVINCIAS_CAT_VARIANTES.items():
        if key in prov_norm or prov_norm in key:
            return True, value
    
    # Fallback: usar el normalizador base
    provincia_normalizada = normalizar_provincia_base(provincia)
    if provincia_normalizada in PROVINCIAS_VALIDAS:
        return True, provincia_normalizada
    
    return False, None


def validar_codigo_postal_provincia(cp: str, provincia: str) -> Tuple[bool, str]:
    """Valida que el código postal corresponda a la provincia."""
    if not cp or len(cp) != 5:
        return False, f"Código postal inválido: {cp}"
    
    # Usar el validador común
    if validar_cp_provincia(cp, provincia):
        return True, ""
    
    return False, f"CP {cp} no corresponde a {provincia}"


def validar_coordenadas(lat: float, lon: float) -> bool:
    """Valida que las coordenadas estén en rango válido para Catalunya."""
    # Rango aproximado de Catalunya (con margen)
    return (40.5 <= lat <= 42.9) and (0.1 <= lon <= 3.4)


def extraer_coordenadas_google_maps(url: str) -> Tuple[Optional[float], Optional[float]]:
    """Extrae coordenadas del parámetro q de la URL de Google Maps.
    
    Ejemplo: http://maps.google.com/maps?t=k&q=41.3028+2.019474
    
    Args:
        url: URL de Google Maps con parámetro q
        
    Returns:
        Tupla (lat, lon) o (None, None) si no se puede extraer
    """
    if not url:
        return None, None
    
    try:
        # Buscar patrón: q=<lat>+<lon> o q=<lat>,<lon> o q=<lat>%20<lon>
        match = re.search(r'[?&]q=([-+]?\d+\.?\d*)[+,\s%20]([-+]?\d+\.?\d*)', url)
        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))
            
            # Validación básica de rangos globales
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    except (ValueError, AttributeError) as e:
        logger.debug(f"Error al extraer coordenadas de URL: {e}")
    
    return None, None


class CatalunyaTransformer:
    """Transformador de datos de Catalunya"""
    
    def transform_item(self, raw: dict) -> Tuple[Optional[EstacionExtraida], Optional[str]]:
        """
        Transforma un item del XML al modelo EstacionExtraida.
        
        Args:
            raw: Diccionario con datos crudos
            
        Returns:
            Tupla (EstacionExtraida, None) si éxito, o (None, "razón error") si falla
        """
        # Extraer campos
        nombre = raw.get("denominaci")
        direccion = raw.get("adre_a")
        municipio = raw.get("municipi")
        provincia_raw = raw.get("serveis_territorials")
        cp_raw = raw.get("cp")
        horario = raw.get("horari_de_servei")
        telefono = raw.get("tel_atenc_public")
        email = raw.get("correu_electr_nic")
        web_url = raw.get("web_url") or raw.get("localitzador_a_google_maps_url")
        
        # Normalizar código postal
        cp = normalize_codigo_postal(cp_raw)
        if cp is None:
            return None, f"Código postal inválido (CP original: {cp_raw})"
        
        # Validar campos obligatorios
        if not nombre or not direccion or not municipio:
            faltantes = []
            if not nombre:
                faltantes.append("nombre")
            if not direccion:
                faltantes.append("dirección")
            if not municipio:
                faltantes.append("municipio")
            return None, f"Campos obligatorios faltantes: {', '.join(faltantes)}"
        
        # Normalizar y validar provincia
        es_valida, provincia = normalizar_provincia(provincia_raw)
        if not es_valida:
            return None, f"Provincia inválida: '{provincia_raw}'"
        
        # Validar CP vs Provincia
        es_valido_cp, msg_cp = validar_codigo_postal_provincia(cp, provincia)
        if not es_valido_cp:
            return None, msg_cp
        
        # Procesar coordenadas desde Google Maps URL (fuente más confiable)
        google_maps_url = raw.get("localitzador_a_google_maps_url")
        
        if not google_maps_url:
            return None, "URL de Google Maps no disponible"
        
        lat, lon = extraer_coordenadas_google_maps(google_maps_url)
        
        if lat is None or lon is None:
            return None, f"No se pudieron extraer coordenadas de Google Maps URL: {google_maps_url}"
        
        # Validar rango de coordenadas
        if not validar_coordenadas(lat, lon):
            return None, f"Coordenadas fuera de rango Catalunya (lat={lat}, lon={lon})"
        
        # Normalizar nombre
        nombre_norm = normalize_estacion_name(nombre)
        
        # Construir contacto
        contacto_parts = []
        if telefono:
            try:
                tel_int = int(telefono)
                contacto_parts.append(f"Tel: {tel_int}")
            except (ValueError, TypeError):
                contacto_parts.append(f"Tel: {telefono}")
        if email and is_valid_email(email):
            contacto_parts.append(f"Email: {email}")
        contacto = " | ".join(contacto_parts) if contacto_parts else None
        
        # Construir modelo
        estacion = EstacionExtraida(
            nombre=nombre_norm,
            tipo=TipoEstacion.ESTACION_FIJA,
            direccion=direccion,
            codigo_postal=cp,
            localidad=municipio,
            provincia=provincia,
            latitud=lat,
            longitud=lon,
            descripcion=None,
            horario=horario,
            contacto=contacto,
            url=web_url
        )
        
        return estacion, None
