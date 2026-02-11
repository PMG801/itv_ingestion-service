import logging
import json
import httpx
from typing import List, Dict, Any

# --- 1. Importar Queries (Capa de Datos) ---
from app.db.load_queries import insertar_estacion, limpiar_tablas, obtener_estaciones_existentes

# --- 2. Importar Extractores (Capa de Integración) ---
# NOTA: Los extractores ahora están en extractor_services/ como microservicios.
# La carpeta extractors/ ha sido eliminada. Este servicio de carga legacy
# necesita ser actualizado para llamar a los microservicios via HTTP.
# 
# TODO: Refactorizar para usar llamadas HTTP a:
#   - http://localhost:8001/extract (Catalunya)
#   - http://localhost:8002/extract (Galicia) 
#   - http://localhost:8003/extract (Valencia)
#
# Por ahora, los extractores no están disponibles y las funciones de carga
# retornarán un error indicando que se deben usar los endpoints de microservicios.

# --- 3. Importar Log Collector ---
from app.db.log_collector import LogCollector

# --- 4. Importar Detector de Duplicados (desde extractor_services/common) ---
from extractor_services.common.duplicate_detector import DetectorDuplicados

logger = logging.getLogger(__name__)

# MAPA DE MICROSERVICIOS EXTRACTORES
# Los extractores han sido migrados a microservicios independientes
# Este mapa configura los endpoints de cada microservicio extractor
EXTRACTOR_MAP = {
    "GAL": {
        "url": "http://localhost:8003/extract",
        "nombre": "Galicia"
    },
    "CAT": {   
        "url": "http://localhost:8002/extract",
        "nombre": "Catalunya"
    },
    "VAL": {   
        "url": "http://localhost:8001/extract",
        "nombre": "Valencia"
    }
}

# FUNCIONES GENÉRICAS

async def ejecutar_carga_fuente(fuente_id: str) -> Dict[str, Any]:
    """
    Ejecuta la carga de datos llamando al microservicio extractor correspondiente.
    
    El microservicio extractor se encargará de:
    1. Extraer datos del archivo fuente
    2. Transformar y normalizar los datos
    3. Enviar al endpoint POST /api/ingest/ de la API central
    
    Args:
        fuente_id: Identificador de la fuente ("GAL", "CAT", "VAL")
        
    Returns:
        Dict con el resultado de la llamada al microservicio
    """
    logs = LogCollector()
    fuente_id = fuente_id.upper()
    
    if fuente_id not in EXTRACTOR_MAP:
        mensaje = f"Fuente '{fuente_id}' no reconocida. Fuentes disponibles: {list(EXTRACTOR_MAP.keys())}"
        logs.error("Fuente no disponible", {"fuente": fuente_id})
        logger.error(mensaje)
        return {
            "status": "error",
            "origin": fuente_id,
            "mensaje": mensaje,
            "logs": logs.get_summary()
        }
    
    config = EXTRACTOR_MAP[fuente_id]
    url = config["url"]
    nombre = config["nombre"]
    
    logs.info(f"Llamando a microservicio {nombre}", {"fuente": fuente_id, "url": url})
    logger.info(f"Iniciando carga de {nombre} via microservicio: {url}")
    
    try:
        # Llamar al microservicio extractor con cliente async
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url)
        
        if response.status_code == 200:
            result = response.json()
            logs.info(f"Carga completada exitosamente", {
                "fuente": fuente_id,
                "insertados": result.get("insertados", 0),
                "fallidos": result.get("fallidos", 0)
            })
            logger.info(f"Carga de {nombre} completada: {result}")
            return {
                "status": "completed",
                "origin": fuente_id,
                "mensaje": f"Carga de {nombre} completada exitosamente",
                "resultado": result,
                "logs": logs.get_summary()
            }
        else:
            mensaje = f"Error al llamar al microservicio: HTTP {response.status_code}"
            logs.error(mensaje, {"fuente": fuente_id, "status": response.status_code})
            logger.error(f"{mensaje} - {response.text}")
            return {
                "status": "error",
                "origin": fuente_id,
                "mensaje": mensaje,
                "logs": logs.get_summary()
            }
            
    except httpx.TimeoutException:
        mensaje = f"Timeout al llamar al microservicio {nombre}"
        logs.error(mensaje, {"fuente": fuente_id})
        logger.error(mensaje)
        return {
            "status": "error",
            "origin": fuente_id,
            "mensaje": mensaje,
            "logs": logs.get_summary()
        }
    except Exception as e:
        mensaje = f"Error al llamar al microservicio {nombre}: {str(e)}"
        logs.error(mensaje, {"fuente": fuente_id, "error": str(e)})
        logger.error(mensaje)
        return {
            "status": "error",
            "origin": fuente_id,
            "mensaje": mensaje,
            "logs": logs.get_summary()
        }



def _ejecutar_carga_fuente_legacy(fuente_id: str) -> Dict[str, Any]:
    """
    [LEGACY - NO USAR] Función antigua que orquestaba el pipeline ETL.
    
    Esta función ha sido deshabilitada porque los extractores han sido
    migrados a microservicios independientes.
    
    Args:
        fuente_id: Identificador de la fuente ("GAL", "CAT", "VAL")
        
    Returns:
        Dict con resumen y logs de la operación
    """
    # Inicializar log collector
    logs = LogCollector()
    
    fuente_id = fuente_id.upper()
    if fuente_id not in EXTRACTOR_MAP or not EXTRACTOR_MAP:
        logs.error("Fuente no disponible o extractores deshabilitados", {"fuente": fuente_id})
        logger.error(f"Fuente no disponible: {fuente_id}")
        return {
            "status": "error",
            "origin": fuente_id,
            "logs": logs.get_summary()
        }

    config_fuente = EXTRACTOR_MAP[fuente_id]
    extractor = config_fuente["extractor"]
    source_path = config_fuente["source_path"]
    
    logs.info(f"Iniciando carga", {"fuente": fuente_id, "archivo": source_path})
    logger.info(f"\n{'='*70}")
    logger.info(f"  🚀 INICIANDO CARGA: {fuente_id}")
    logger.info(f"{'='*70}")
    logger.info(f"📁 Archivo fuente: {source_path}")

    # EJECUTAR PIPELINE COMPLETO (Extract -> Transform -> Detect Duplicates)
    # El método run() de BaseExtractor ya incluye la detección de duplicados
    try:
        resultado_pipeline = extractor.run(source_path)
        modelos_unicos = resultado_pipeline['exitosos']
        rechazados_transformacion = resultado_pipeline['rechazados_transformacion']
        
        logs.info(f"Pipeline completado", {"estaciones_unicas": len(modelos_unicos)})
        logger.info(f"✅ Pipeline completado: {len(modelos_unicos)} estaciones únicas listas para insertar")
        
        # Registrar los rechazados en transformación como errores
        for num_registro, nombre_estacion, razon in rechazados_transformacion:
            logs.error(f"Rechazo en transformación - Registro {num_registro}", {
                "nombre": nombre_estacion,
                "razon": razon
            })
            logger.warning(f"   ⚠️ Registro {num_registro} rechazado en transformación: {razon}")
            
    except Exception as e:
        logs.error(f"Error en pipeline de extracción", {
            "fuente": fuente_id,
            "error": str(e)
        })
        logger.error(f"❌ Error en pipeline de extracción {fuente_id}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "origin": fuente_id,
            "logs": logs.get_summary()
        }

    if not modelos_unicos:
        logs.warning(f"No hay estaciones para insertar", {})
        logger.warning(f"⚠️ No hay estaciones para insertar")
        return {
            "status": "completed",
            "origin": fuente_id,
            "estaciones_unicas": 0,
            "insertados_ok": 0,
            "fallidos": 0,
            "logs": logs.get_summary()
        }

    # FILTRAR DUPLICADOS CONTRA LA BASE DE DATOS
    logger.info(f"\n🔍 Verificando duplicados contra la base de datos...")
    estaciones_existentes = obtener_estaciones_existentes()
    duplicados_bd = []
    
    if estaciones_existentes:
        detector = DetectorDuplicados()
        estaciones_nuevas = []
        
        for modelo_nuevo in modelos_unicos:
            es_duplicado_bd = False
            criterio_aplicado = None
            
            # Comparar con cada estación existente
            for est_existente in estaciones_existentes:
                es_dup, criterio = detector.son_duplicados(modelo_nuevo, est_existente)
                if es_dup:
                    es_duplicado_bd = True
                    criterio_aplicado = criterio
                    duplicados_bd.append({
                        'nueva': modelo_nuevo.get('nombre', 'SIN NOMBRE'),
                        'existente': est_existente.get('nombre', 'SIN NOMBRE'),
                        'criterio': criterio
                    })
                    break
            
            if not es_duplicado_bd:
                estaciones_nuevas.append(modelo_nuevo)
        
        # Loguear duplicados encontrados contra BD
        if duplicados_bd:
            logs.info(f"Duplicados vs BD detectados", {"total": len(duplicados_bd)})
            logger.info(f"⚠️ Se encontraron {len(duplicados_bd)} duplicados contra la BD:")
            for i, dup in enumerate(duplicados_bd[:5], 1):  # Mostrar solo los primeros 5
                logger.info(f"   {i}. '{dup['nueva']}' duplica a '{dup['existente']}' (criterio: {dup['criterio']})")
            if len(duplicados_bd) > 5:
                logger.info(f"   ... y {len(duplicados_bd) - 5} más")
        
        logger.info(f"✅ Estaciones nuevas a insertar: {len(estaciones_nuevas)} de {len(modelos_unicos)}")
        modelos_unicos = estaciones_nuevas
    else:
        logger.info(f"✅ Base de datos vacía, todas las estaciones son nuevas")

    if not modelos_unicos:
        logs.warning(f"No hay estaciones nuevas para insertar (todas son duplicadas)", {})
        logger.warning(f"⚠️ No hay estaciones nuevas para insertar (todas ya existen en la BD)")
        return {
            "status": "completed",
            "origin": fuente_id,
            "estaciones_unicas": 0,
            "insertados_ok": 0,
            "fallidos": 0,
            "duplicados_bd": len(duplicados_bd) if estaciones_existentes else 0,
            "logs": logs.get_summary()
        }

    # INSERTAR en base de datos
    logger.info(f"\n💾 Insertando {len(modelos_unicos)} estaciones en la base de datos...")
    for i, modelo in enumerate(modelos_unicos, 1):
        nombre_estacion = modelo.get('nombre', 'SIN NOMBRE')
        
        # insertar_estacion ahora retorna (bool, str) - (éxito, mensaje_error)
        exitoso, mensaje_error = insertar_estacion(modelo)
        
        if exitoso:
            logs.success(f"Estación cargada", {
                "numero": i,
                "nombre": nombre_estacion
            })
        else:
            logs.error(f"Error carga registro {i}", {
                "nombre": nombre_estacion,
                "razon": mensaje_error
            })
            logger.error(f"   ❌ Error insertando estación {i}: {nombre_estacion} - {mensaje_error}")

    resumen = {
        "status": "completed",
        "origin": fuente_id,
        "estaciones_unicas": len(modelos_unicos),
        "insertados_ok": logs.stats["exitosos"],
        "fallidos": logs.stats["fallidos"],
        "duplicados_bd": len(duplicados_bd),
        "logs": logs.get_summary()
    }
    
    logger.info(f"\n{'='*70}")
    logger.info(f"  ✅ CARGA COMPLETADA: {fuente_id}")
    logger.info(f"{'='*70}")
    logger.info(f"  📊 Estaciones únicas procesadas: {len(modelos_unicos)}")
    logger.info(f"  ✅ Insertadas correctamente:     {logs.stats['exitosos']}")
    logger.info(f"  ❌ Errores de inserción:         {logs.stats['fallidos']}")
    if duplicados_bd:
        logger.info(f"  🔄 Duplicados vs BD descartados: {len(duplicados_bd)}")
    logger.info(f"{'='*70}\n")
    
    return resumen


def ejecutar_carga_multiple(fuentes: List[str]) -> Dict[str, Any]:
    """
    Ejecuta carga para múltiples fuentes y devuelve resumen consolidado
    """
    resultados = {}
    total_insertados = 0
    total_fallidos = 0
    
    for fuente in fuentes:
        logger.info(f"Procesando fuente: {fuente}")
        resultado = ejecutar_carga_fuente(fuente)
        resultados[fuente] = resultado
        
        if "insertados_ok" in resultado:
            total_insertados += resultado["insertados_ok"]
        if "fallidos" in resultado:
            total_fallidos += resultado["fallidos"]
    
    resumen_consolidado = {
        "status": "completado",
        "total_fuentes": len(fuentes),
        "total_insertados": total_insertados,
        "total_fallidos": total_fallidos,
        "resultados_por_fuente": resultados
    }
    
    return resumen_consolidado


def limpiar_todas_las_tablas():
    """
    Función de utilidad para borrar los datos antes de una carga.
    """
    logger.warning("Iniciando borrado de todas las tablas de carga...")
    try:
        resultado = limpiar_tablas()
        if resultado.get("status") == "ok":
            logger.info("Borrado completado: %s", resultado.get("deleted"))
        else:
            logger.error("Fallo al borrar tablas: %s", resultado.get("msg"))
        return resultado
    except Exception as e:
        logger.error(f"Error al limpiar tablas: {e}")
        return {"status": "error", "msg": str(e)}
