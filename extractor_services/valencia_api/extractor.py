"""
Servicio de extracción para Valencia.
Lee el archivo JSON de ITVs y lo transforma al formato estandarizado.
"""
import json
import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import (
    PayloadExtraccion,
    EstacionExtraida,
    RegistroRechazado,
    EstadisticasExtraccion,
    TipoEstacion
)
from transformer import ValenciaTransformer

logger = logging.getLogger(__name__)


class ValenciaExtractorService:
    """Servicio de extracción para datos de Valencia"""
    
    def __init__(self):
        self.transformer = ValenciaTransformer()
    
    def extract_raw(self, source_path: str) -> List[Dict[str, Any]]:
        """
        Extrae datos crudos del archivo JSON de Valencia.
        
        Args:
            source_path: Ruta al archivo JSON
            
        Returns:
            Lista de diccionarios con los datos crudos
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Archivo no encontrado: {source_path}")
        
        logger.info(f"📂 Leyendo archivo: {source_path}")
        
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Asegurar que siempre es una lista
        if isinstance(data, dict):
            data = [data]
        
        logger.info(f"📊 Extraídos {len(data)} registros crudos")
        return data
    
    def extract_and_transform(self, source_path: str) -> PayloadExtraccion:
        """
        Ejecuta el pipeline completo de extracción y transformación.
        
        Args:
            source_path: Ruta al archivo fuente
            
        Returns:
            PayloadExtraccion con los datos transformados
        """
        # 1. Extraer datos crudos
        raw_data = self.extract_raw(source_path)
        total_raw = len(raw_data)
        
        # 2. Transformar cada registro
        estaciones: List[EstacionExtraida] = []
        rechazados: List[RegistroRechazado] = []
        
        for i, item in enumerate(raw_data, 1):
            try:
                resultado, error = self.transformer.transform_item(item)
                
                if resultado:
                    estaciones.append(resultado)
                else:
                    nombre = item.get('DIRECCIÓN') or item.get('MUNICIPIO') or 'SIN NOMBRE'
                    rechazados.append(RegistroRechazado(
                        registro=i,
                        nombre=nombre,
                        razon=error or "Error desconocido"
                    ))
                    
            except Exception as e:
                nombre = item.get('DIRECCIÓN') or 'SIN NOMBRE'
                logger.error(f"❌ Error transformando registro {i}: {e}")
                rechazados.append(RegistroRechazado(
                    registro=i,
                    nombre=nombre,
                    razon=f"Error durante transformación: {str(e)}"
                ))
        
        # 3. Construir estadísticas
        stats = EstadisticasExtraccion(
            total_raw=total_raw,
            transformados=len(estaciones),
            rechazados=len(rechazados)
        )
        
        logger.info(f"✅ Transformación completada: {len(estaciones)} exitosas, {len(rechazados)} rechazadas")
        
        # 4. Construir payload
        return PayloadExtraccion(
            source="VAL",
            timestamp=datetime.utcnow(),
            estaciones=estaciones,
            rechazados=rechazados,
            stats=stats
        )
