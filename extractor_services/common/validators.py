"""Validadores para datos de estaciones ITV.

Incluye validación de provincias, códigos postales, campos obligatorios y detección de duplicados.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from unidecode import unidecode
from .spanish_locations import (
    PROVINCIAS_VALIDAS,
    normalizar_provincia,
    validar_codigo_postal,
    obtener_provincia_por_codigo_postal,
    obtener_rango_coordenadas_provincia,
    RANGO_COORDENADAS_ESPANA
)
from .schemas import TipoEstacion

logger = logging.getLogger(__name__)


def validar_provincia(provincia: str) -> Tuple[bool, Optional[str]]:
    """Valida que una provincia esté en la lista de provincias válidas.
    
    Args:
        provincia: Nombre de la provincia a validar
        
    Returns:
        Tuple con (es_valida, provincia_normalizada)
    """
    if not provincia:
        logger.warning("Provincia vacía o None")
        return False, None
    
    provincia_normalizada = normalizar_provincia(provincia)
    
    if provincia_normalizada not in PROVINCIAS_VALIDAS:
        logger.warning(f"❌ Provincia no válida: '{provincia}' (normalizada: '{provincia_normalizada}')")
        return False, None
    
    return True, provincia_normalizada


def normalizar_municipio(municipio: str) -> str:
    """Normaliza nombre de municipio para comparación.
    
    Args:
        municipio: Nombre del municipio
        
    Returns:
        Nombre normalizado (sin acentos, minúsculas, sin espacios extra)
    """
    if not municipio:
        return ""
    
    # Eliminar acentos y convertir a minúsculas
    normalizado = unidecode(municipio.strip().lower())
    
    # Normalizar variantes comunes
    normalizaciones = {
        "hospitalet de llobregat": "l'hospitalet de llobregat",
        "el prat de llobregat": "el prat de llobregat",
        "sant": "san",
        "santa": "santa",
    }
    
    for variante, oficial in normalizaciones.items():
        if variante in normalizado:
            normalizado = normalizado.replace(variante, oficial)
    
    return normalizado


def validar_ubicacion_por_codigo_postal(
    codigo_postal: str, 
    provincia: str, 
    municipio: Optional[str] = None
) -> Tuple[bool, str]:
    """Valida que un código postal pertenezca a una provincia.
    
    Args:
        codigo_postal: Código postal de la estación (5 dígitos)
        provincia: Nombre de la provincia declarada
        municipio: Nombre del municipio (opcional, para logging)
        
    Returns:
        Tuple con (es_valido, mensaje_error)
    """
    if not codigo_postal:
        return False, "Código postal vacío"
    
    # Validar formato del código postal
    codigo_limpio = codigo_postal.strip()
    if not codigo_limpio.isdigit() or len(codigo_limpio) != 5:
        return False, f"Código postal con formato inválido: '{codigo_postal}'"
    
    # Normalizar provincia
    es_valida, provincia_normalizada = validar_provincia(provincia)
    if not es_valida:
        return False, f"Provincia no válida: '{provincia}'"
    
    # Validar que el código postal corresponda a la provincia
    if not validar_codigo_postal(codigo_limpio, provincia_normalizada):
        # Intentar detectar la provincia correcta según el código postal
        provincia_detectada = obtener_provincia_por_codigo_postal(codigo_limpio)
        
        if provincia_detectada:
            mensaje = (f"Código postal {codigo_limpio} no corresponde a {provincia_normalizada}. "
                      f"Según el código postal, debería ser: {provincia_detectada}")
        else:
            mensaje = f"Código postal {codigo_limpio} no válido para {provincia_normalizada}"
        
        if municipio:
            mensaje += f" (municipio: {municipio})"
        
        logger.warning(f"❌ {mensaje}")
        return False, mensaje
    
    return True, ""


def validar_coordenadas(
    latitud: Optional[float],
    longitud: Optional[float],
    provincia: Optional[str] = None,
    nombre_estacion: str = "Estación",
    tipo_estacion: Optional[TipoEstacion] = None
) -> bool:
    """Valida que las coordenadas estén dentro de rangos válidos.
    
    Args:
        latitud: Latitud de la estación
        longitud: Longitud de la estación
        provincia: Nombre de la provincia (opcional, para validación más estricta)
        nombre_estacion: Nombre de la estación para logging
        tipo_estacion: Tipo de estación (opcional). Si es OTROS (agrícola móvil), no se validan coordenadas
        
    Returns:
        True si las coordenadas son válidas o no existen, False si son inválidas
    """
    # Si la estación es tipo OTROS o ESTACION_MOVIL, no validar coordenadas
    if tipo_estacion == TipoEstacion.OTROS or tipo_estacion == TipoEstacion.ESTACION_MOVIL:
        logger.info(f"⏭️ Estación tipo OTROS (agrícola): no se validan coordenadas - '{nombre_estacion}'")
        return True
    
    # Si no hay coordenadas, no es un error crítico (algunas estaciones pueden no tenerlas)
    if latitud is None or longitud is None:
        return True
    
    try:
        lat = float(latitud)
        lon = float(longitud)
    except (ValueError, TypeError):
        logger.warning(f"❌ Coordenadas inválidas (no numéricas) en '{nombre_estacion}': lat={latitud}, lon={longitud}")
        return False
    
    # Validar que no sean (0, 0) - valor por defecto que indica error
    if lat == 0.0 and lon == 0.0:
        logger.warning(f"⚠️ Coordenadas en (0, 0) en '{nombre_estacion}' - probablemente error de extracción")
        return True  # No rechazar, pero advertir
    
    # 1. Validar rango general de España
    lat_min, lat_max, lon_min, lon_max = RANGO_COORDENADAS_ESPANA
    
    if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
        logger.warning(f"❌ Coordenadas fuera de España en '{nombre_estacion}': lat={lat}, lon={lon}")
        return False
    
    # 2. Si se proporciona provincia, validar rango específico
    if provincia:
        es_valida, provincia_normalizada = validar_provincia(provincia)
        if es_valida:
            lat_min_prov, lat_max_prov, lon_min_prov, lon_max_prov = obtener_rango_coordenadas_provincia(provincia_normalizada)
            
            # Margen de tolerancia de 0.2 grados (~20 km) para casos en límites provinciales
            margen = 0.2
            
            if not (lat_min_prov - margen <= lat <= lat_max_prov + margen and 
                    lon_min_prov - margen <= lon <= lon_max_prov + margen):
                logger.warning(f"❌ Coordenadas fuera de la provincia '{provincia_normalizada}' en '{nombre_estacion}': lat={lat}, lon={lon}")
                logger.info(f"   Rango esperado: lat=[{lat_min_prov}, {lat_max_prov}], lon=[{lon_min_prov}, {lon_max_prov}]")
                return False
    
    return True


def validar_campos_obligatorios(
    estacion: Dict[str, Any],
    campos_requeridos: Optional[List[str]] = None
) -> Tuple[bool, List[str]]:
    """Valida que una estación tenga los campos obligatorios.
    
    Args:
        estacion: Diccionario con los datos de la estación
        campos_requeridos: Lista de campos que deben estar presentes y no vacíos
                          Si es None, usa una lista por defecto
        
    Returns:
        Tuple con (es_valida, lista_campos_faltantes)
    """
    if campos_requeridos is None:
        campos_requeridos = ["nombre", "direccion", "codigo_postal"]
    
    campos_faltantes = []
    
    for campo in campos_requeridos:
        valor = estacion.get(campo)
        
        # Verificar que el campo existe y no está vacío
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            campos_faltantes.append(campo)
    
    es_valida = len(campos_faltantes) == 0
    
    if not es_valida:
        logger.warning(f"❌ Estación rechazada: faltan campos obligatorios {campos_faltantes} - {estacion.get('nombre', 'SIN NOMBRE')}")
    
    return es_valida, campos_faltantes


def validar_estacion_completa(
    estacion: Dict[str, Any],
    provincia: Optional[str] = None,
    municipio: Optional[str] = None,
    origen: str = "Desconocido"
) -> bool:
    """Validación completa de una estación ITV.
    
    Args:
        estacion: Diccionario con los datos de la estación
        provincia: Nombre de la provincia (opcional si ya está en estacion)
        municipio: Nombre del municipio (opcional si ya está en estacion)
        origen: Nombre de la fuente de datos para logging
        
    Returns:
        True si la estación es válida
    """
    # 1. Validar campos obligatorios
    es_valida, campos_faltantes = validar_campos_obligatorios(estacion)
    if not es_valida:
        logger.warning(f"[{origen}] Estación rechazada: faltan campos {campos_faltantes}")
        return False
    
    # 2. Validar provincia (si se proporciona)
    if provincia:
        es_valida_prov, provincia_norm = validar_provincia(provincia)
        if not es_valida_prov:
            logger.warning(f"[{origen}] Estación rechazada: provincia inválida '{provincia}' - {estacion.get('nombre')}")
            return False
        
        # 3. Validar código postal (si se proporciona y provincia es válida)
        codigo_postal = estacion.get('codigo_postal')
        if codigo_postal:
            es_valido_cp, mensaje_error = validar_ubicacion_por_codigo_postal(
                codigo_postal, 
                provincia_norm,
                municipio
            )
            if not es_valido_cp:
                logger.warning(f"[{origen}] Estación rechazada: {mensaje_error} - {estacion.get('nombre')}")
                return False
    
    return True


def log_estadisticas_validacion(
    total_raw: int,
    total_transformados: int,
    total_validos: int,
    duplicados_eliminados: int,
    origen: str = "Extractor"
):
    """Registra estadísticas de validación.
    
    Args:
        total_raw: Total de registros crudos
        total_transformados: Total después de transformación
        total_validos: Total después de validación
        duplicados_eliminados: Cantidad de duplicados eliminados
        origen: Nombre del extractor para logging
    """
    rechazados_transformacion = total_raw - total_transformados
    rechazados_validacion = total_transformados - total_validos - duplicados_eliminados
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 ESTADÍSTICAS DE VALIDACIÓN - {origen}")
    logger.info(f"{'='*60}")
    logger.info(f"  • Registros crudos:              {total_raw}")
    logger.info(f"  • Rechazados en transformación:  {rechazados_transformacion}")
    logger.info(f"  • Transformados correctamente:   {total_transformados}")
    logger.info(f"  • Rechazados en validación:      {rechazados_validacion}")
    logger.info(f"  • Duplicados eliminados:         {duplicados_eliminados}")
    logger.info(f"  • ✅ Estaciones válidas finales: {total_validos}")
    logger.info(f"{'='*60}\n")


def validar_estacion_agricola_moviles(codigo_postal: Optional[str], tipo: TipoEstacion) -> Tuple[bool, Optional[str]]:
    """Valida que las estaciones agrícolas o móviles no tengan código postal.
    
    Las estaciones agrícolas o móviles no deben tener código postal ya que son móviles.
    Si tienen código postal, es probable que sea inventado y se debe rechazar.
    
    Args:
        codigo_postal: Código postal de la estación
        tipo: Tipo de estación
        
    Returns:
        Tuple con (es_valida, mensaje_error). 
        Si es_valida=True, mensaje_error=None.
        Si es_valida=False, mensaje_error contiene la razón del rechazo.
    """
    # Solo aplicar esta validación a estaciones tipo OTROS o ESTACION_MOVIL (agrícolas o móviles)
    if tipo != TipoEstacion.OTROS and tipo != TipoEstacion.ESTACION_MOVIL:
        return True, None
    
    # Las estaciones agrícolas o móviles NO deben tener código postal
    if codigo_postal is not None and codigo_postal.strip():
        logger.warning(f"❌ Estación agrícola o móvil rechazada: tiene código postal '{codigo_postal}' (probablemente inventado)")
        return False, f"Estación agrícola o móvil no puede tener código postal (CP inventado: {codigo_postal})"
    
    return True, None
