"""  
Queries de búsqueda de estaciones ITV.

Este módulo contiene las funciones para buscar estaciones en la base de datos
aplicando diversos filtros geográficos y de tipo.

Funciones principales:
- search_stations: Búsqueda de estaciones con filtros opcionales
- get_provinces: Obtener lista de provincias disponibles
"""

import logging
from typing import List, Optional, Dict
from app.db.connection import DatabaseConnection

logger = logging.getLogger(__name__)

async def search_stations(
    localidad: Optional[str] = None,
    codigo_postal: Optional[str] = None,
    provincia: Optional[str] = None,
    tipo: Optional[str] = None
) -> List[Dict]:
    """
    Busca estaciones en la base de datos aplicando filtros opcionales.
    
    Realiza un JOIN con las tablas Localidad y Provincia para obtener los
    nombres descriptivos completos. La búsqueda es case-insensitive y permite
    coincidencias parciales (ILIKE) excepto para el tipo de estación.
    
    Args:
        localidad: Filtro parcial por nombre de localidad (ILIKE %localidad%).
        codigo_postal: Filtro por código postal (prefijo o exacto).
        provincia: Filtro parcial por nombre de provincia (ILIKE %provincia%).
        tipo: Filtro por tipo de estación. Valores esperados:
              - "fija" o "movil": busca valores exactos en BD
              - Otros: búsqueda con ILIKE
        
    Returns:
        List[Dict]: Lista de estaciones encontradas. Cada estación es un diccionario con:
                    - nombre: Nombre de la estación
                    - direccion: Dirección completa
                    - localidad: Nombre de la localidad
                    - codigo_postal: Código postal
                    - provincia: Nombre de la provincia
                    - descripcion: Descripción adicional
                    - tipo: Tipo de estación (estacion_fija, estacion_movil, otros)
                    - latitud: Coordenada latitud
                    - longitud: Coordenada longitud
                    
    Note:
        Si no se especifican filtros, devuelve TODAS las estaciones.
        Los resultados se ordenan alfabéticamente por nombre.
    """
    
    # Consulta base con JOINs para obtener nombres descriptivos
    # JOIN con localidad para obtener el nombre del municipio
    # JOIN con provincia para obtener el nombre de la provincia
    query = """
    SELECT 
        e.nombre,
        e.direccion,
        l.nombre as localidad,
        e.codigo_postal,
        p.nombre as provincia,
        e.descripcion,
        e.tipo,
        e.latitud,
        e.longitud
    FROM estacion e
    JOIN localidad l ON e.localidad_codigo = l.codigo
    JOIN provincia p ON l.provincia_codigo = p.codigo
    WHERE 1=1
    """
    
    params = []
    
    # === Construcción dinámica de filtros ===
    # Usamos ILIKE para búsquedas insensibles a mayúsculas/minúsculas
    # El patrón %...% permite coincidencias parciales
    
# Filtro por localidad (coincidencia parcial)
    if localidad:
        query += " AND l.nombre ILIKE %s"
        params.append(f"%{localidad}%")
        
    # Filtro por código postal (prefijo o exacto)
    if codigo_postal:
        query += " AND e.codigo_postal ILIKE %s"
        params.append(f"{codigo_postal}%")
        
    # Filtro por provincia (coincidencia parcial)
    if provincia:
        query += " AND p.nombre ILIKE %s"
        params.append(f"%{provincia}%")
        
    # Filtro por tipo de estación
    # Valores en BD: estacion_fija, estacion_movil, otros
    if tipo:
        tipo_lower = tipo.lower()
        if "movil" in tipo_lower or "móvil" in tipo_lower:
             # Buscar estacion_movil (valor exacto en BD)
             query += " AND e.tipo = %s"
             params.append("estacion_movil")
        elif "fija" in tipo_lower:
             # Buscar estacion_fija (valor exacto en BD)
             query += " AND e.tipo = %s"
             params.append("estacion_fija")
        elif "otros" in tipo_lower:
             # Buscar otros (valor exacto en BD)
             query += " AND e.tipo = %s"
             params.append("otros")
        else:
             # Búsqueda genérica con ILIKE para casos no previstos
             query += " AND e.tipo ILIKE %s"
             params.append(f"%{tipo}%")
        
    # Ordenar resultados alfabéticamente por nombre de estación
    query += " ORDER BY e.nombre ASC;"
    
    # Log de debug para rastrear queries ejecutadas
    logger.info(f"Query generada: {query}")
    logger.info(f"Parámetros: {params}")
    
    try:
        # Ejecutar consulta usando el pool de conexiones async
        rows = await DatabaseConnection.execute_query(query, tuple(params))
        
        # Mapear tuplas a diccionarios
        # DatabaseConnection.execute_query devuelve lista de tuplas (fetchall)
        # Necesitamos convertirlas a diccionarios para que Pydantic las serialice
        results = []
        for row in rows:
            # row es una tupla, mapear índices a campos
            estacion = {
                "nombre": row[0],
                "direccion": row[1],
                "localidad": row[2],
                "codigo_postal": row[3],
                "provincia": row[4],
                "descripcion": row[5],
                "tipo": row[6],
                "latitud": row[7],
                "longitud": row[8]
            }
            results.append(estacion)
            
        logger.info(f"Búsqueda de estaciones retornó {len(results)} resultados.")
        return results
        
    except Exception as e:
        logger.error(f"Error ejecutando búsqueda de estaciones: {e}")
        # Relanzamos para que el controller maneje el 500
        raise e

async def get_all_provinces() -> List[Dict]:
    """
    Obtiene todas las provincias disponibles en la base de datos, ordenadas alfabéticamente.
    
    Returns:
        List[Dict]: Lista de provincias con id y nombre.
    """
    query = "SELECT codigo, nombre FROM provincia ORDER BY nombre ASC;"
    
    try:
        rows = await DatabaseConnection.execute_query(query)
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "nombre": row[1]
            })
            
        logger.info(f"Consulta de provincias retornó {len(results)} resultados.")
        return results
        
    except Exception as e:
        logger.error(f"Error consultando provincias: {e}")
        raise e
