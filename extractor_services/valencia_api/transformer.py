"""
Transformador de datos de Valencia.
Convierte los datos crudos del JSON al formato estandarizado EstacionExtraida.

NOTA: Esta versión NO interactúa con la base de datos. 
Solo transforma los datos para enviarlos a la API central.
"""
import re
import logging
from typing import Optional, Tuple

import sys
import os

# Add parent directory to path for relative imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import EstacionExtraida, TipoEstacion
from common.normalizers import (
    normalize_codigo_postal,
    normalize_direccion,
    normalize_schedule,
    normalize_tipo_estacion
)
from common.spanish_locations import (
    PROVINCIAS_VALIDAS,
    normalizar_provincia as normalizar_provincia_base,
    validar_codigo_postal as validar_cp_provincia
)
from common.validators import validar_estacion_agricola_moviles, validar_coordenadas

# Import geocoding from the same directory
from geocoding import buscar_coords_nominatim

logger = logging.getLogger(__name__)


# ===== VALIDATORS =====

# Provincias de la Comunidad Valenciana con variantes de nombres
PROVINCIAS_CV_VARIANTES = {
    "alicante": "Alicante",
    "alacant": "Alicante",
    "castellon": "Castellón",
    "castelló": "Castellón",
    "castello": "Castellón",
    "valencia": "Valencia",
    "valència": "Valencia",
}


def normalizar_provincia(provincia: str) -> Optional[str]:
    """Normaliza el nombre de provincia a formato estándar."""
    if not provincia:
        return None
    
    from unidecode import unidecode
    prov_norm = unidecode(provincia.strip().lower())
    
    # Primero intentar con las variantes locales de Valencia
    if prov_norm in PROVINCIAS_CV_VARIANTES:
        return PROVINCIAS_CV_VARIANTES[prov_norm]
    
    # Fallback: usar el normalizador base
    provincia_normalizada = normalizar_provincia_base(provincia)
    if provincia_normalizada in PROVINCIAS_VALIDAS:
        return provincia_normalizada
    
    return provincia.title()


def validar_codigo_postal_provincia(cp: str, provincia: str) -> Tuple[bool, str]:
    """Valida que el código postal corresponda a la provincia."""
    if not cp or len(cp) != 5:
        return False, f"Código postal inválido: {cp}"
    
    # Usar el validador común
    if validar_cp_provincia(cp, provincia):
        return True, ""
    
    return False, f"CP {cp} no corresponde a {provincia}"


class ValenciaTransformer:
    """Transformador de datos de Valencia"""
    
    def transform_item(self, raw: dict) -> Tuple[Optional[EstacionExtraida], Optional[str]]:
        """
        Transforma un item del JSON al modelo EstacionExtraida.
        
        Args:
            raw: Diccionario con datos crudos
            
        Returns:
            Tupla (EstacionExtraida, None) si éxito, o (None, "razón error") si falla
        """
        # Extraer campos
        direccion = raw.get("DIRECCIÓN")
        municipio = raw.get("MUNICIPIO")
        provincia_raw = raw.get("PROVINCIA")
        cp_raw = raw.get("C.POSTAL")
        tipo_raw = raw.get("TIPO ESTACIÓN")
        horario_raw = raw.get("HORARIOS")
        correo_raw = raw.get("CORREO")
        
        # Normalizar tipo primero para saber si es agrícola/móvil
        horario = normalize_schedule(horario_raw)
        tipo_str = normalize_tipo_estacion(tipo_raw)
        tipo = TipoEstacion(tipo_str)
        
        # Validar estaciones agrícolas o móviles (tipo OTROS o ESTACION_MOVIL) - no deben tener CP
        # Usar el valor raw para verificar si existe (sin normalizar)
        if tipo == TipoEstacion.OTROS or tipo == TipoEstacion.ESTACION_MOVIL:
            if cp_raw is not None and str(cp_raw).strip():
                return None, f"Estación agrícola o móvil no puede tener código postal (CP inventado: {cp_raw})"
            cp = None  # No normalizar CP para agrícolas/móviles
        else:
            # Solo normalizar CP para estaciones fijas
            cp = normalize_codigo_postal(cp_raw)
            if cp is None:
                return None, f"Código postal inválido o faltante (obligatorio para fijas): '{cp_raw}'"
        
        # Validar campos obligatorios
        if tipo == TipoEstacion.ESTACION_FIJA and not municipio:
            return None, "Municipio faltante (obligatorio para estaciones fijas)"
        
        if not direccion:
            return None, "Dirección faltante"
        
        # Normalizar provincia
        provincia = normalizar_provincia(provincia_raw) if provincia_raw else None
        
        if not provincia and tipo == TipoEstacion.ESTACION_FIJA:
            return None, "Provincia no especificada (requerida para estaciones fijas)"
        
        # Validar CP vs Provincia (solo para estaciones fijas que tienen CP)
        if tipo == TipoEstacion.ESTACION_FIJA and cp and provincia:
            es_valido, msg = validar_codigo_postal_provincia(cp, provincia)
            if not es_valido:
                return None, msg
        
        # Generar nombre
        nombre = self._generar_nombre(tipo, direccion, municipio)
        
        # Obtener coordenadas (usando geocoding sin Selenium)
        # Para estaciones agrícolas o móviles (tipo OTROS o ESTACION_MOVIL), las coordenadas pueden ser aproximadas
        lat, lon = buscar_coords_nominatim(direccion, municipio, provincia)
        
        # Para estaciones agrícolas (OTROS) o móviles, no rechazar si no se encuentran coordenadas
        if lat is None or lon is None:
            if tipo == TipoEstacion.ESTACION_FIJA:
                # Solo rechazar estaciones fijas sin coordenadas
                return None, f"No se pudieron obtener coordenadas para: {direccion}, {municipio}"
            else:
                # Para móviles y agrícolas, usar coordenadas por defecto (0, 0)
                # NOTA: El frontend debe filtrar coordenadas (0, 0) y no mostrarlas en el mapa
                logger.warning(f"⚠️ No se encontraron coordenadas para estación {tipo.value}: {nombre}. Se usarán coordenadas (0, 0).")
                lat, lon = 0.0, 0.0
        
        # Validar coordenadas (se salta validación para tipo OTROS o ESTACION_MOVIL)
        if not validar_coordenadas(lat, lon, provincia, nombre, tipo):
            return None, f"Coordenadas inválidas o fuera de rango para: {nombre}"
        
        # Determinar localidad
        if tipo == TipoEstacion.ESTACION_MOVIL:
            localidad = "Móvil"
        elif tipo == TipoEstacion.OTROS:
            localidad = "Agrícola"
        else:
            localidad = municipio or "Desconocida"
        
        # Construir modelo
        estacion = EstacionExtraida(
            nombre=nombre,
            tipo=tipo,
            direccion=normalize_direccion(direccion),
            codigo_postal=cp if tipo != TipoEstacion.OTROS and tipo != TipoEstacion.ESTACION_MOVIL else None,  # Estaciones agrícolas o móviles no tienen CP
            localidad=localidad,
            provincia=provincia or "Desconocida",
            latitud=lat,
            longitud=lon,
            descripcion=None,
            horario=horario,
            contacto=correo_raw,
            url="https://sitval.com"
        )
        
        return estacion, None
    
    def _generar_nombre(self, tipo: TipoEstacion, direccion: str, municipio: Optional[str]) -> str:
        """Genera el nombre de la estación según su tipo."""
        if tipo == TipoEstacion.ESTACION_MOVIL:
            nombre_base = direccion.replace("I.T.V.", "ITV").replace("Móvil", "móvil")
            return f"Estación {nombre_base}"
        elif tipo == TipoEstacion.OTROS:  # Agrícola
            nombre_base = direccion.replace("I.T.V.", "ITV").replace("Agrícola", "agrícola")
            return f"Estación {nombre_base}"
        elif municipio:
            return f"Estación ITV de {municipio}"
        else:
            nombre_base = direccion.replace("I.T.V.", "ITV")
            return f"Estación {nombre_base}"
