"""
Servicio de extracción para Catalunya.
Lee el archivo XML de ITVs y lo transforma al formato estandarizado.
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
from transformer import CatalunyaTransformer

logger = logging.getLogger(__name__)


class CatalunyaExtractorService:
    """Servicio de extracción para datos de Catalunya"""
    
    def __init__(self):
        self.transformer = CatalunyaTransformer()
    
    def extract_raw(self, source_path: str) -> List[Dict[str, Any]]:
        """
        Extrae datos crudos del archivo XML de Catalunya usando pandas.
        
        Args:
            source_path: Ruta al archivo XML
            
        Returns:
            Lista de diccionarios con los datos crudos
        """
        import pandas as pd
        
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Archivo no encontrado: {source_path}")
        
        logger.info(f"📂 Leyendo archivo XML: {source_path}")
        
        try:
            # XSLT para transformar atributos como 'url' en elementos
            stylesheet = """
            <xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
                <xsl:output method="xml" omit-xml-declaration="yes" indent="yes"/>
                <xsl:strip-space elements="*"/>

                <!-- Identity transform -->
                <xsl:template match="node()|@*">
                    <xsl:copy>
                        <xsl:apply-templates select="node()|@*"/>
                    </xsl:copy>
                </xsl:template>

                <!-- Transform elements with 'url' attribute -->
                <xsl:template match="*[@url]">
                    <!-- Keep the original element -->
                    <xsl:copy>
                        <xsl:apply-templates select="node()|@*"/>
                    </xsl:copy>
                    <!-- Add a new element with suffix _url -->
                    <xsl:element name="{name()}_url">
                        <xsl:value-of select="@url"/>
                    </xsl:element>
                </xsl:template>
            </xsl:stylesheet>
            """
            
            df = pd.read_xml(
                source_path,
                xpath=".//row/row",
                stylesheet=stylesheet
            )
            
            # Convertir DataFrame a lista de diccionarios
            data = json.loads(df.to_json(orient='records', force_ascii=False))
            
            logger.info(f"📊 Extraídos {len(data)} registros crudos")
            return data
            
        except Exception as e:
            logger.error(f"❌ Error leyendo XML: {e}")
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
                    nombre = item.get('denominaci') or 'SIN NOMBRE'
                    rechazados.append(RegistroRechazado(
                        registro=i,
                        nombre=nombre,
                        razon=error or "Error desconocido"
                    ))
                    
            except Exception as e:
                nombre = item.get('denominaci') or 'SIN NOMBRE'
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
            source="CAT",
            timestamp=datetime.utcnow(),
            estaciones=estaciones,
            rechazados=rechazados,
            stats=stats
        )
