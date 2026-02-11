"""
Servicio de extracción para Galicia.
Lee el archivo CSV de ITVs y lo transforma al formato estandarizado.
"""
import os
import logging
import json
from typing import List, Dict, Any
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
from transformer import GaliciaTransformer

logger = logging.getLogger(__name__)


class GaliciaExtractorService:
    """Servicio de extracción para datos de Galicia"""
    
    def __init__(self):
        self.transformer = GaliciaTransformer()
    
    def extract_raw(self, source_path: str) -> List[Dict[str, Any]]:
        """
        Extrae datos crudos del archivo CSV de Galicia usando pandas.
        
        Args:
            source_path: Ruta al archivo CSV
            
        Returns:
            Lista de diccionarios con los datos crudos
        """
        import pandas as pd
        
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Archivo no encontrado: {source_path}")
        
        logger.info(f"📂 Leyendo archivo CSV: {source_path}")
        
        try:
            df = pd.read_csv(source_path, sep=';', encoding='latin1')
            
            # Convertir DataFrame a lista de diccionarios
            data = json.loads(df.to_json(orient='records', force_ascii=False))
            
            logger.info(f"📊 Extraídos {len(data)} registros crudos")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error leyendo CSV: {e}")
            raise
    
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
                    nombre = (item.get('NOME DA ESTACIÓN') or 
                             item.get('nome_da_estacion') or 
                             'SIN NOMBRE')
                    rechazados.append(RegistroRechazado(
                        registro=i,
                        nombre=nombre,
                        razon=error or "Error desconocido"
                    ))
                    
            except Exception as e:
                nombre = item.get('NOME DA ESTACIÓN') or 'SIN NOMBRE'
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
            source="GAL",
            timestamp=datetime.utcnow(),
            estaciones=estaciones,
            rechazados=rechazados,
            stats=stats
        )
