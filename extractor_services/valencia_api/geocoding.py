"""
Geocoding usando APIs gratuitas (sin Selenium).
Alternativa ligera para los microservicios.
"""
import logging
import httpx
from typing import Tuple, Optional
import time

logger = logging.getLogger(__name__)

# Cache simple en memoria para evitar peticiones repetidas
_coords_cache: dict = {}

# Control de rate limiting (Nominatim requiere mínimo 1 seg entre peticiones)
_last_request_time: float = 0


def buscar_coords_nominatim(
    direccion: str, 
    municipio: Optional[str], 
    provincia: Optional[str]
) -> Tuple[Optional[float], Optional[float]]:
    """
    Busca coordenadas usando la API de Nominatim (OpenStreetMap).
    
    Args:
        direccion: Dirección de la estación
        municipio: Nombre del municipio
        provincia: Nombre de la provincia
        
    Returns:
        Tupla (latitud, longitud) o (None, None) si no se encuentra
    """
    # Construir query
    parts = [p for p in [direccion, municipio, provincia, "España"] if p]
    query = ", ".join(parts)
    
    # Verificar cache
    if query in _coords_cache:
        logger.debug(f"📍 Cache hit: {query}")
        return _coords_cache[query]
    
    logger.info(f"🔍 Geocoding: {query}")
    
    # Respetar rate limit de Nominatim (mínimo 1 seg entre peticiones)
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 1.5:  # 1.5 seg para dar margen
        wait_time = 1.5 - elapsed
        logger.debug(f"⏱️ Esperando {wait_time:.2f}s por rate limit")
        time.sleep(wait_time)
    
    try:
        # Usar Nominatim (OpenStreetMap)
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "es"
        }
        headers = {
            "User-Agent": "ITV-Extractor/1.0 (dev@gmail.com)"
        }
        
        _last_request_time = time.time()
        
        with httpx.Client(timeout=30) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            results = response.json()
            
            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                
                # Guardar en cache
                _coords_cache[query] = (lat, lon)
                
                logger.info(f"✅ Coordenadas encontradas: {lat}, {lon}")
                return lat, lon
            
            logger.warning(f"⚠️ No se encontraron coordenadas para: {query}")
            
            # Intentar búsqueda más simple (solo municipio + provincia)
            if municipio and provincia:
                return _buscar_fallback(municipio, provincia)
            
            return None, None
            
    except Exception as e:
        logger.error(f"❌ Error en geocoding: {e}")
        
        # Intentar fallback
        if municipio and provincia:
            return _buscar_fallback(municipio, provincia)
        
        return None, None


def _buscar_fallback(municipio: str, provincia: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Búsqueda de fallback solo con municipio y provincia.
    """
    query = f"{municipio}, {provincia}, España"
    
    if query in _coords_cache:
        return _coords_cache[query]
    
    logger.info(f"🔄 Fallback geocoding: {query}")
    
    # Respetar rate limit de Nominatim
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 1.5:
        wait_time = 1.5 - elapsed
        logger.debug(f"⏱️ Esperando {wait_time:.2f}s por rate limit")
        time.sleep(wait_time)
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "es"
        }
        headers = {
            "User-Agent": "ITV-Extractor/1.0 (dev@gmail.com)"
        }
        
        _last_request_time = time.time()
        
        with httpx.Client(timeout=30) as client:
            response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            results = response.json()
            
            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                _coords_cache[query] = (lat, lon)
                logger.info(f"✅ Fallback exitoso: {lat}, {lon}")
                return lat, lon
        
        return None, None
        
    except Exception as e:
        logger.error(f"❌ Error en fallback: {e}")
        return None, None


# ===== Coordenadas predefinidas para testing =====
# Útil cuando no hay conexión o para tests
COORDS_VALENCIA_DEFAULT = {
    "Valencia": (39.4699, -0.3763),
    "Alicante": (38.3452, -0.4810),
    "Castellón": (39.9864, -0.0513),
}


def buscar_coords_mock(
    direccion: str, 
    municipio: Optional[str], 
    provincia: Optional[str]
) -> Tuple[Optional[float], Optional[float]]:
    """
    Versión mock para testing sin conexión.
    Devuelve coordenadas aproximadas basadas en la provincia.
    """
    if provincia in COORDS_VALENCIA_DEFAULT:
        base = COORDS_VALENCIA_DEFAULT[provincia]
        # Añadir pequeña variación para diferenciar estaciones
        import random
        lat = base[0] + random.uniform(-0.1, 0.1)
        lon = base[1] + random.uniform(-0.1, 0.1)
        return lat, lon
    
    # Default: Valencia centro
    return 39.4699, -0.3763
