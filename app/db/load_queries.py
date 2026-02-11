"""  
Queries de carga de datos a la base de datos.

Este módulo contiene las funciones para insertar datos de estaciones ITV
en la base de datos PostgreSQL.

Funciones principales:
- buscar_o_crear_provincia: Gestiona la tabla de provincias
- buscar_o_crear_localidad: Gestiona la tabla de localidades
- insertar_estacion: Inserta nuevas estaciones
- obtener_estaciones_existentes: Obtiene estaciones para detección de duplicados

Nota: Todas las funciones manejan concurrencia y errores de FK adecuadamente.
"""

import psycopg
from typing import Dict, Any, List
from app.db.connection import get_db_connection
import logging

logger = logging.getLogger(__name__)

def buscar_o_crear_provincia(nombre: str) -> int:
    """
    Busca una provincia por nombre o la crea si no existe.
    
    Esta función implementa el patrón "upsert" (update or insert) de forma segura,
    manejando condiciones de concurrencia cuando múltiples procesos intentan crear
    la misma provincia simultáneamente.
    
    Args:
        nombre: Nombre de la provincia (ej: "A Coruña", "Madrid").
    
    Returns:
        int: Código (ID) autogenerado de la provincia, o None si hay error.
        
    Note:
        - Si la provincia ya existe, devuelve su ID sin crear duplicados
        - Si no existe, la crea y devuelve el nuevo ID
        - Maneja UniqueViolation en caso de concurrencia
    """
    if not nombre:
        logger.warning(f"Intento de buscar Provincia con nombre nulo. Saltando.")
        return None
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Paso 1: Buscar provincia existente por nombre
            cursor.execute("SELECT codigo FROM provincia WHERE nombre = %s;", (nombre,))
            result = cursor.fetchone()
            if result:
                return result[0]  # Provincia encontrada, devolver ID
            
            # Paso 2: Provincia no existe, intentar crearla
            try:
                sql = "INSERT INTO provincia (nombre) VALUES (%s) RETURNING codigo;"
                cursor.execute(sql, (nombre,))
                conn.commit()
                provincia_id = cursor.fetchone()[0]
                logger.info(f"Provincia creada: '{nombre}' con ID {provincia_id}")
                return provincia_id
            except psycopg.errors.UniqueViolation:
                # Condición de concurrencia: otro proceso la creó mientras tanto
                conn.rollback()
                logger.debug(f"Concurrencia detectada para Provincia: {nombre}. Reintentando búsqueda.")
                cursor.execute("SELECT codigo FROM provincia WHERE nombre = %s;", (nombre,))
                res = cursor.fetchone()
                return res[0] if res else None
            except Exception as e:
                logger.error(f"Error al insertar Provincia '{nombre}': {e}")
                conn.rollback()
                return None


def buscar_o_crear_localidad(nombre: str, provincia_id: int) -> int:
    """
    Busca una localidad por nombre y provincia, o la crea si no existe.
    
    Esta función implementa el patrón "upsert" con manejo de foreign keys.
    Una localidad se identifica únicamente por la combinación de nombre + provincia.
    
    Args:
        nombre: Nombre de la localidad/municipio (ej: "Santiago de Compostela").
        provincia_id: Código (ID) de la provincia a la que pertenece (FK).
    
    Returns:
        int: Código (ID) autogenerado de la localidad, o None si hay error.
        
    Note:
        - Valida que provincia_id exista antes de insertar (foreign key)
        - Maneja UniqueViolation en caso de concurrencia
        - Retorna None si la provincia no existe
    """
    if not nombre or not provincia_id:
        logger.warning(f"Intento de buscar Localidad con datos nulos. Nombre: {nombre}, FK_Prov: {provincia_id}. Saltando.")
        return None

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Paso 1: Buscar localidad existente por nombre Y provincia
            cursor.execute(
                "SELECT codigo FROM localidad WHERE nombre = %s AND provincia_codigo = %s;",
                (nombre, provincia_id)
            )
            result = cursor.fetchone()
            if result:
                return result[0]  # Localidad encontrada
            
            # Paso 2: Localidad no existe, intentar crearla
            try:
                sql = "INSERT INTO localidad (nombre, provincia_codigo) VALUES (%s, %s) RETURNING codigo;"
                cursor.execute(sql, (nombre, provincia_id))
                conn.commit()
                localidad_id = cursor.fetchone()[0]
                logger.info(f"Localidad creada: '{nombre}' (provincia_id={provincia_id}) con ID {localidad_id}")
                return localidad_id
            except psycopg.errors.UniqueViolation:
                # Condición de concurrencia
                conn.rollback()
                logger.debug(f"Concurrencia detectada para Localidad: {nombre}. Reintentando búsqueda.")
                cursor.execute(
                    "SELECT codigo FROM localidad WHERE nombre = %s AND provincia_codigo = %s;",
                    (nombre, provincia_id)
                )
                res = cursor.fetchone()
                return res[0] if res else None
            except psycopg.errors.ForeignKeyViolation:
                # La provincia no existe en la BD
                logger.error(f"Error de FK: La provincia con ID {provincia_id} no existe. No se puede insertar Localidad '{nombre}'.")
                conn.rollback()
                return None
            except Exception as e:
                logger.error(f"Error al insertar Localidad '{nombre}': {e}")
                conn.rollback()
                return None

def insertar_estacion(datos: Dict[str, Any]) -> tuple[bool, str]:
    """
    Inserta una nueva estación ITV en la base de datos.
    
    Esta función valida los datos mínimos requeridos e intenta insertar la estación.
    El código de estación (cod_estacion) se genera automáticamente en la BD.
    
    Args:
        datos: Diccionario con los datos de la estación. Campos:
               - nombre (requerido): Nombre de la estación
               - localidad_codigo (requerido): FK a la tabla localidad
               - tipo: Tipo de estación (estacion_fija/estacion_movil/otros)
               - direccion: Dirección completa
               - codigo_postal: Código postal (string)
               - latitud: Coordenada latitud (decimal)
               - longitud: Coordenada longitud (decimal)
               - descripcion: Texto descriptivo
               - horario: Horario de atención
               - contacto: Teléfono/email de contacto
               - url: Página web de la estación
    
    Returns:
        tuple[bool, str]: 
            - bool: True si la inserción fue exitosa, False en caso contrario
            - str: Mensaje de error (vacío si fue exitoso)
            
    Note:
        - El campo 'cod_estacion' se excluye si está presente (se autogenera)
        - Valida foreign key a localidad
        - Maneja errores de rangos numéricos (coordenadas)
        - Detecta duplicados (UniqueViolation)
    """
    if not datos.get('nombre') or not datos.get('localidad_codigo'):
        msg = f"Datos insuficientes: nombre='{datos.get('nombre')}', localidad_codigo={datos.get('localidad_codigo')}"
        logger.warning(f"Estación rechazada: {msg}")
        return False, msg
    
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            try:
                # Filtrar datos: excluir cod_estacion (auto-generado)
                datos_filtrados = {k: v for k, v in datos.items() if k != 'cod_estacion'}
                
                columnas = ', '.join(datos_filtrados.keys())
                placeholders = ', '.join(['%s'] * len(datos_filtrados))
                valores = tuple(datos_filtrados.values())

                # INSERT simple: PostgreSQL auto-genera cod_estacion
                sql = f"""
                INSERT INTO estacion ({columnas})
                VALUES ({placeholders});
                """
                
                cursor.execute(sql, valores)
                conn.commit()
                logger.info(f"Estación '{datos.get('nombre')}' insertada exitosamente.")
                return True, ""
            except psycopg.errors.ForeignKeyViolation:
                msg = f"FK error - Localidad con ID {datos.get('localidad_codigo')} no existe"
                logger.error(f"Error al insertar Estación '{datos.get('nombre')}': {msg}")
                conn.rollback()
                return False, msg
            except psycopg.errors.NumericValueOutOfRange as e:
                msg = f"Valor numérico fuera de rango (probablemente coordenadas): {str(e)}"
                logger.error(f"Error al insertar Estación '{datos.get('nombre')}': {msg}")
                conn.rollback()
                return False, msg
            except psycopg.errors.StringDataRightTruncation as e:
                msg = f"Dato demasiado largo para la columna"
                logger.error(f"Error al insertar Estación '{datos.get('nombre')}': {msg}")
                conn.rollback()
                return False, msg
            except psycopg.errors.UniqueViolation as e:
                msg = f"Registro duplicado (ya existe)"
                logger.error(f"Error al insertar Estación '{datos.get('nombre')}': {msg}")
                conn.rollback()
                return False, msg
            except Exception as e:
                msg = f"{type(e).__name__}: {str(e)}"
                logger.error(f"Error al insertar Estación '{datos.get('nombre')}': {msg}")
                conn.rollback()
                return False, msg


def obtener_estaciones_existentes() -> List[Dict[str, Any]]:
    """
    Obtiene todas las estaciones existentes en la base de datos.
    
    Esta función se utiliza para la detección de duplicados antes de insertar
    nuevas estaciones. Recupera solo los campos necesarios para la comparación.
    
    Returns:
        List[Dict[str, Any]]: Lista de diccionarios con los datos de cada estación:
            - nombre: Nombre de la estación
            - codigo_postal: Código postal
            - direccion: Dirección completa
            - latitud: Coordenada latitud
            - longitud: Coordenada longitud
            
    Note:
        - Retorna lista vacía en caso de error
        - Usada por el detector de duplicados para evitar insertar estaciones repetidas
        - En bases de datos grandes, considerar paginación o cacheo
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            try:
                # Seleccionar solo campos necesarios para detección de duplicados
                sql = """
                SELECT nombre, codigo_postal, direccion, latitud, longitud
                FROM estacion;
                """
                cursor.execute(sql)
                rows = cursor.fetchall()
                
                # Convertir tuplas a diccionarios para fácil acceso
                estaciones = []
                for row in rows:
                    estaciones.append({
                        'nombre': row[0],
                        'codigo_postal': row[1],
                        'direccion': row[2],
                        'latitud': row[3],
                        'longitud': row[4]
                    })
                
                logger.info(f"Recuperadas {len(estaciones)} estaciones existentes de la BD")
                return estaciones
            except Exception as e:
                logger.error(f"Error al obtener estaciones existentes: {e}")
                return []


def limpiar_tablas() -> Dict[str, Any]:
    """Trunca las tablas de carga: Estacion, Localidad, Provincia.

    Devuelve un dict con el estado y los conteos previos (si se pudieron obtener).
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            try:
                try:
                    cur.execute("SELECT count(*) FROM estacion;")
                    est_before = cur.fetchone()[0]
                except Exception:
                    est_before = None

                try:
                    cur.execute("SELECT count(*) FROM localidad;")
                    loc_before = cur.fetchone()[0]
                except Exception:
                    loc_before = None

                try:
                    cur.execute("SELECT count(*) FROM provincia;")
                    prov_before = cur.fetchone()[0]
                except Exception:
                    prov_before = None

                cur.execute("TRUNCATE TABLE estacion, localidad, provincia RESTART IDENTITY CASCADE;")
                conn.commit()

                return {
                    "status": "ok",
                    "deleted": {
                        "estacion": est_before,
                        "localidad": loc_before,
                        "provincia": prov_before,
                    },
                }
            except Exception as e:
                conn.rollback()
                logger.error("Error al truncar tablas: %s", e)
                return {"status": "error", "msg": str(e)}