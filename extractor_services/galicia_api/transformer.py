"""
Transformador de datos de Galicia.
Convierte los datos crudos del CSV al formato estandarizado EstacionExtraida.

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
    normalize_schedule,
    capitalize_provincia,
    parse_coordinates,
    find_column,
    safe_get,
    separate_email_and_url
)
from common.spanish_locations import (
    PROVINCIAS_VALIDAS,
    normalizar_provincia as normalizar_provincia_base,
    validar_codigo_postal as validar_cp_provincia
)

logger = logging.getLogger(__name__)


# ===== VALIDATORS =====

# Provincias de Galicia con variantes de nombres
PROVINCIAS_GAL_VARIANTES = {
    "a coruña": "A Coruña",
    "a coruna": "A Coruña",
    "la coruña": "A Coruña",
    "lugo": "Lugo",
    "ourense": "Ourense",
    "orense": "Ourense",
    "pontevedra": "Pontevedra",
}


def normalizar_provincia(provincia: str) -> Tuple[bool, Optional[str]]:
    """Normaliza y valida provincia gallega."""
    if not provincia:
        return False, None
    
    from unidecode import unidecode
    prov_norm = unidecode(provincia.strip().lower())
    
    # Primero intentar con las variantes locales de Galicia
    if prov_norm in PROVINCIAS_GAL_VARIANTES:
        return True, PROVINCIAS_GAL_VARIANTES[prov_norm]
    
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
    """Valida que las coordenadas estén en rango válido para Galicia."""
    # Rango aproximado de Galicia (con margen)
    return (41.8 <= lat <= 44.0) and (-9.3 <= lon <= -6.7)


class GaliciaTransformer:
    """Transformador de datos de Galicia"""
    
    def transform_item(self, raw: dict) -> Tuple[Optional[EstacionExtraida], Optional[str]]:
        """
        Transforma un item del CSV al modelo EstacionExtraida.
        
        Args:
            raw: Diccionario con datos crudos
            
        Returns:
            Tupla (EstacionExtraida, None) si éxito, o (None, "razón error") si falla
        """
        # Buscar columnas (los CSV gallegos pueden tener nombres variados)
        col_nombre = find_column(raw, 'nome_da_estacion', 'nombre', 'nombre_de_la_estacion')
        col_direccion = find_column(raw, 'enderezo', 'direccion', 'endereco')
        col_concello = find_column(raw, 'concello', 'municipio')
        col_provincia = find_column(raw, 'provincia')
        col_cp = find_column(raw, 'codigo_postal', 'cp')
        col_coords = find_column(raw, 'coordenadas_gmaps', 'coordenadas', 'coords')
        col_tel = find_column(raw, 'telefono', 'tel')
        col_email = find_column(raw, 'correo_electronico', 'email', 'correo')
        col_horario = find_column(raw, 'horario')
        col_web = find_column(raw, 'solicitude_de_cita_previa', 'url_cita', 'web')
        
        # Extraer valores
        nombre_raw = safe_get(raw, col_nombre)
        direccion = safe_get(raw, col_direccion)
        municipio = safe_get(raw, col_concello)
        provincia_raw = safe_get(raw, col_provincia)
        cp_raw = safe_get(raw, col_cp)
        coords_raw = safe_get(raw, col_coords)
        horario_raw = safe_get(raw, col_horario)
        tel_raw = safe_get(raw, col_tel)
        email_raw = safe_get(raw, col_email)
        web_raw = safe_get(raw, col_web)
        
        # Validar coordenadas
        if not coords_raw or coords_raw.strip() == "":
            return None, "Coordenadas vacías o faltantes"
        
        lat, lon = parse_coordinates(coords_raw)
        if lat is None or lon is None:
            return None, f"Error al parsear coordenadas (coords_raw={coords_raw})"
        
        if not validar_coordenadas(lat, lon):
            return None, f"Coordenadas fuera de rango Galicia (lat={lat}, lon={lon})"
        
        # Normalizar código postal
        cp = normalize_codigo_postal(cp_raw)
        if cp is None:
            return None, f"Código postal inválido (CP original: {cp_raw})"
        
        # Validar campos obligatorios
        if not nombre_raw or not direccion or not municipio:
            faltantes = []
            if not nombre_raw:
                faltantes.append("nombre")
            if not direccion:
                faltantes.append("dirección")
            if not municipio:
                faltantes.append("municipio")
            return None, f"Campos obligatorios faltantes: {', '.join(faltantes)}"
        
        # Normalizar y validar provincia
        provincia_cap = capitalize_provincia(provincia_raw) if provincia_raw else None
        if not provincia_cap:
            return None, "Provincia no especificada"
        
        es_valida, provincia = normalizar_provincia(provincia_cap)
        if not es_valida:
            return None, f"Provincia inválida: '{provincia_raw}'"
        
        # Validar CP vs Provincia
        es_valido_cp, msg_cp = validar_codigo_postal_provincia(cp, provincia)
        if not es_valido_cp:
            return None, msg_cp
        
        # Normalizar nombre
        nombre = normalize_estacion_name(nombre_raw)
        
        # Normalizar horario
        horario = normalize_schedule(horario_raw)
        
        # Separar email y URL
        email, url_from_email = separate_email_and_url(email_raw)
        url = web_raw or url_from_email
        
        # Construir contacto
        contacto_parts = []
        if tel_raw:
            try:
                tel_int = int(tel_raw)
                contacto_parts.append(f"Tel: {tel_int}")
            except (ValueError, TypeError):
                contacto_parts.append(f"Tel: {tel_raw}")
        if email:
            contacto_parts.append(f"Email: {email}")
        contacto = " | ".join(contacto_parts) if contacto_parts else None
        
        # Construir modelo
        estacion = EstacionExtraida(
            nombre=nombre,
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
            url=url
        )
        
        return estacion, None
