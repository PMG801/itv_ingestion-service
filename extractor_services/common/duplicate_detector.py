"""Detector de estaciones duplicadas.

Proporciona clases y funciones para detectar y eliminar estaciones ITV duplicadas
usando múltiples criterios configurables.
"""

import logging
from math import radians, sin, cos, sqrt, atan2
from typing import Dict, Any, List, Optional, Tuple
from unidecode import unidecode

logger = logging.getLogger(__name__)


def normalizar_para_comparacion(texto: str) -> str:
    """Normaliza texto para comparación: sin acentos, minúsculas, sin espacios extra."""
    if not texto:
        return ""
    texto_norm = unidecode(str(texto).strip().lower())
    # Remover espacios extra y caracteres especiales comunes
    texto_norm = " ".join(texto_norm.split())
    return texto_norm


def extraer_nombre_base(nombre: str) -> str:
    """Extrae el nombre base de una estación, removiendo prefijos comunes.
    
    Args:
        nombre: Nombre de la estación
        
    Returns:
        Nombre base normalizado
    """
    nombre_norm = normalizar_para_comparacion(nombre)
    
    # Remover prefijos comunes
    prefijos = ["estacion itv de", "estacion itv", "itv"]
    for prefijo in prefijos:
        if nombre_norm.startswith(prefijo):
            nombre_norm = nombre_norm[len(prefijo):].strip()
    
    return nombre_norm


def calcular_distancia_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia en metros entre dos puntos geográficos usando la fórmula de Haversine.
    
    Args:
        lat1, lon1: Coordenadas del primer punto
        lat2, lon2: Coordenadas del segundo punto
        
    Returns:
        Distancia en metros
    """
    R = 6371000  # Radio de la Tierra en metros
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c


class CriterioDuplicado:
    """Clase base para criterios de detección de duplicados."""
    
    def __init__(self, nombre: str):
        self.nombre = nombre
    
    def es_duplicado(self, est1: Dict[str, Any], est2: Dict[str, Any]) -> bool:
        """Determina si dos estaciones son duplicadas según este criterio."""
        raise NotImplementedError


class CriterioNombreCodigoPostal(CriterioDuplicado):
    """Criterio: Mismo nombre base + mismo código postal."""
    
    def __init__(self):
        super().__init__("nombre + código postal")
    
    def es_duplicado(self, est1: Dict[str, Any], est2: Dict[str, Any]) -> bool:
        nombre_base1 = extraer_nombre_base(est1.get("nombre", ""))
        nombre_base2 = extraer_nombre_base(est2.get("nombre", ""))
        
        if not nombre_base1 or not nombre_base2 or nombre_base1 != nombre_base2:
            return False
        
        cp1 = est1.get("codigo_postal")
        cp2 = est2.get("codigo_postal")
        
        return cp1 and cp2 and str(cp1).strip() == str(cp2).strip()


class CriterioNombreDireccion(CriterioDuplicado):
    """Criterio: Mismo nombre normalizado + misma dirección normalizada."""
    
    def __init__(self):
        super().__init__("nombre + dirección")
    
    def es_duplicado(self, est1: Dict[str, Any], est2: Dict[str, Any]) -> bool:
        nombre1 = normalizar_para_comparacion(est1.get("nombre", ""))
        nombre2 = normalizar_para_comparacion(est2.get("nombre", ""))
        
        if not nombre1 or not nombre2 or nombre1 != nombre2:
            return False
        
        dir1 = normalizar_para_comparacion(est1.get("direccion", ""))
        dir2 = normalizar_para_comparacion(est2.get("direccion", ""))
        
        return dir1 and dir2 and dir1 == dir2


class CriterioCoordenadas(CriterioDuplicado):
    """Criterio: Coordenadas muy cercanas (< umbral_metros) + nombre base similar."""
    
    def __init__(self, umbral_metros: float = 100.0):
        super().__init__(f"coordenadas (< {umbral_metros}m)")
        self.umbral_metros = umbral_metros
    
    def es_duplicado(self, est1: Dict[str, Any], est2: Dict[str, Any]) -> bool:
        # Verificar que ambas tienen coordenadas
        lat1 = est1.get("latitud")
        lon1 = est1.get("longitud")
        lat2 = est2.get("latitud")
        lon2 = est2.get("longitud")
        
        if not all([lat1, lon1, lat2, lon2]):
            return False
        
        try:
            lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        except (ValueError, TypeError):
            return False
        
        # Verificar que los nombres base son similares
        nombre_base1 = extraer_nombre_base(est1.get("nombre", ""))
        nombre_base2 = extraer_nombre_base(est2.get("nombre", ""))
        
        if not nombre_base1 or not nombre_base2 or nombre_base1 != nombre_base2:
            return False
        
        # Calcular distancia
        distancia = calcular_distancia_haversine(lat1, lon1, lat2, lon2)
        
        return distancia < self.umbral_metros


class DetectorDuplicados:
    """Detector de estaciones duplicadas con múltiples criterios configurables."""
    
    def __init__(self, criterios: Optional[List[CriterioDuplicado]] = None):
        """Inicializa el detector con criterios de duplicación.
        
        Args:
            criterios: Lista de criterios a aplicar. Si es None, usa criterios por defecto.
        """
        if criterios is None:
            # Criterios por defecto, ordenados por precisión
            self.criterios = [
                CriterioNombreCodigoPostal(),
                CriterioNombreDireccion(),
                CriterioCoordenadas(umbral_metros=100.0)
            ]
        else:
            self.criterios = criterios
    
    def son_duplicados(self, est1: Dict[str, Any], est2: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Determina si dos estaciones son duplicadas aplicando los criterios configurados.
        
        Args:
            est1: Primera estación
            est2: Segunda estación
            
        Returns:
            Tuple (es_duplicado, criterio_aplicado)
        """
        for criterio in self.criterios:
            if criterio.es_duplicado(est1, est2):
                return True, criterio.nombre
        
        return False, None
    
    def detectar_duplicados_optimizado(
        self, 
        estaciones: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int, Dict[str, int]]:
        """Detecta y elimina duplicados usando índices para optimización O(n).
        
        Estrategia:
        1. Usa un diccionario hash para detección rápida por clave única
        2. Solo hace comparación detallada cuando hay colisión de hash
        
        Args:
            estaciones: Lista de estaciones a procesar
            
        Returns:
            Tuple con (lista_sin_duplicados, total_duplicados, estadisticas_por_criterio)
        """
        if not estaciones:
            return [], 0, {}
        
        # Índice: clave_hash -> lista de estaciones con esa clave
        indice_estaciones: Dict[str, List[Dict[str, Any]]] = {}
        duplicados_count = 0
        estadisticas_criterios: Dict[str, int] = {c.nombre: 0 for c in self.criterios}
        
        for estacion_actual in estaciones:
            # Generar clave hash rápida (nombre_base + CP)
            clave_hash = self._generar_clave_hash(estacion_actual)
            
            # Si la clave no existe, es la primera con esa clave
            if clave_hash not in indice_estaciones:
                indice_estaciones[clave_hash] = [estacion_actual]
                continue
            
            # Si existe, comparar con las estaciones que tienen la misma clave
            es_duplicado = False
            criterio_detectado = None
            
            for estacion_existente in indice_estaciones[clave_hash]:
                es_dup, criterio = self.son_duplicados(estacion_actual, estacion_existente)
                if es_dup:
                    es_duplicado = True
                    criterio_detectado = criterio
                    break
            
            if es_duplicado:
                duplicados_count += 1
                if criterio_detectado:
                    estadisticas_criterios[criterio_detectado] += 1
                    logger.debug(f"🗑️ Duplicado ({criterio_detectado}): {estacion_actual.get('nombre', 'SIN NOMBRE')}")
            else:
                # No es duplicado, agregarlo al índice
                indice_estaciones[clave_hash].append(estacion_actual)
        
        # Aplanar el índice para obtener la lista final
        estaciones_unicas = [
            estacion 
            for estaciones_grupo in indice_estaciones.values() 
            for estacion in estaciones_grupo
        ]
        
        # Log resumen
        if duplicados_count > 0:
            logger.info(f"✅ Se eliminaron {duplicados_count} duplicados de {len(estaciones)} estaciones")
            for criterio, count in estadisticas_criterios.items():
                if count > 0:
                    logger.info(f"   • {criterio}: {count}")
        else:
            logger.info(f"✅ No se encontraron duplicados en {len(estaciones)} estaciones")
        
        return estaciones_unicas, duplicados_count, estadisticas_criterios
    
    def _generar_clave_hash(self, estacion: Dict[str, Any]) -> str:
        """Genera una clave hash para agrupación rápida.
        
        Agrupa estaciones con el mismo nombre base y código postal.
        """
        nombre_base = extraer_nombre_base(estacion.get("nombre", ""))
        cp = str(estacion.get("codigo_postal", "")).strip()
        
        return f"{nombre_base}|{cp}"


def detectar_duplicados(estaciones: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Detecta y elimina estaciones duplicadas de una lista.
    
    Función de compatibilidad que usa el nuevo DetectorDuplicados.
    
    Args:
        estaciones: Lista de diccionarios con datos de estaciones
        
    Returns:
        Tuple con (lista_sin_duplicados, cantidad_duplicados_eliminados)
    """
    detector = DetectorDuplicados()
    estaciones_unicas, duplicados_count, _ = detector.detectar_duplicados_optimizado(estaciones)
    return estaciones_unicas, duplicados_count


# Alias para compatibilidad con el código existente
DuplicateFilter = DetectorDuplicados
