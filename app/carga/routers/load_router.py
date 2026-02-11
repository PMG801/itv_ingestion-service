from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
import logging
from datetime import datetime
from app.services.load_service import ejecutar_carga_fuente, EXTRACTOR_MAP, limpiar_todas_las_tablas

router = APIRouter(
    prefix="/api/carga",
    tags=["Carga de Datos"]
)
logger = logging.getLogger(__name__)

# Almacenamiento temporal de resultados de carga (en memoria)
# En producción, usar Redis o BD
carga_resultados = {}

class CargaRequest(BaseModel):
    fuente: str

class LogEntry(BaseModel):
    level: str
    message: str
    details: dict = {}
    timestamp: str

class LoadStats(BaseModel):
    total: int
    exitosos: int
    fallidos: int
    advertencias: int

class LogSummary(BaseModel):
    stats: LoadStats
    logs: list[LogEntry]

class CargaResponse(BaseModel):
    status: str
    origen: str
    mensaje: str
    timestamp: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "accepted",
                "origen": "GAL",
                "mensaje": "Carga para la fuente 'GAL' iniciada en segundo plano.",
                "timestamp": "2024-12-04T15:30:45.123456Z"
            }
        }

class CargaCompletadaResponse(BaseModel):
    status: str
    origin: str
    estaciones_unicas: int
    insertados_ok: int
    fallidos: int
    logs: LogSummary

    class Config:
        json_schema_extra = {
            "example": {
                "status": "completed",
                "origin": "GAL",
                "estaciones_unicas": 45,
                "insertados_ok": 43,
                "fallidos": 2,
                "logs": {
                    "stats": {
                        "total": 45,
                        "exitosos": 43,
                        "fallidos": 2,
                        "advertencias": 0
                    },
                    "logs": [
                        {
                            "level": "info",
                            "message": "Iniciando carga",
                            "details": {"fuente": "GAL", "archivo": "estaciones_gal.csv"},
                            "timestamp": "2024-12-04T15:30:45.123456Z"
                        },
                        {
                            "level": "success",
                            "message": "Estación cargada",
                            "details": {"numero": 1, "nombre": "Estación A Coruña"},
                            "timestamp": "2024-12-04T15:30:46.123456Z"
                        },
                        {
                            "level": "error",
                            "message": "Error carga registro 5",
                            "details": {"nombre": "Estación Inválida", "razon": "Código postal fuera de rango"},
                            "timestamp": "2024-12-04T15:30:47.123456Z"
                        }
                    ]
                }
            }
        }

async def ejecutar_carga_con_almacenamiento(fuente: str):
    """Ejecuta carga y almacena el resultado para consulta posterior"""
    try:
        logger.info(f"Ejecutando carga en background para {fuente}")
        resultado = await ejecutar_carga_fuente(fuente)
        
        logger.debug(f"Resultado de ejecutar_carga_fuente para {fuente}: {resultado}")
        
        # Transformar resultado al formato esperado por el frontend
        default_logs = {"stats": {"total": 0, "exitosos": 0, "fallidos": 0, "advertencias": 0}, "logs": []}
        
        if resultado.get("status") == "completed" and "resultado" in resultado:
            extractor_result = resultado["resultado"]
            logger.debug(f"Extractor result para {fuente}: {extractor_result}")
            
            respuesta_central = extractor_result.get("respuesta_central")
            logger.debug(f"Respuesta central para {fuente}: {respuesta_central}")
            
            if respuesta_central is None:
                respuesta_central = {}
            
            # Si respuesta_central es un objeto Pydantic, convertir a dict
            if hasattr(respuesta_central, 'model_dump'):
                respuesta_central = respuesta_central.model_dump()
            elif hasattr(respuesta_central, 'dict'):
                respuesta_central = respuesta_central.dict()
            
            # Extraer logs - pueden venir directamente o dentro de respuesta_central
            logs_data = respuesta_central.get("logs", default_logs)
            
            # Si logs_data es None o no tiene la estructura esperada, usar default
            if not logs_data or not isinstance(logs_data, dict):
                logs_data = default_logs
            
            logger.info(f"Logs extraídos para {fuente}: {logs_data}")
            
            carga_resultados[fuente] = {
                "status": "completed",
                "origin": fuente,
                "estaciones_unicas": respuesta_central.get("recibidos", 0),
                "insertados_ok": respuesta_central.get("insertados", 0),
                "fallidos": respuesta_central.get("errores_insercion", 0),
                "logs": logs_data
            }
        else:
            # Error en la carga
            error_msg = resultado.get("mensaje", resultado.get("error", "Error desconocido"))
            carga_resultados[fuente] = {
                "status": "error",
                "origin": fuente,
                "estaciones_unicas": 0,
                "insertados_ok": 0,
                "fallidos": 0,
                "logs": {"stats": {"total": 0, "exitosos": 0, "fallidos": 0, "advertencias": 0}, "logs": [{"level": "error", "message": error_msg, "details": {}, "timestamp": datetime.utcnow().isoformat()}]}
            }
        
        logger.info(f"Resultado de carga para {fuente} almacenado en memoria: {carga_resultados[fuente]}")
    except Exception as e:
        logger.error(f"Error en carga background para {fuente}: {e}", exc_info=True)
        carga_resultados[fuente] = {
            "status": "error",
            "origin": fuente,
            "estaciones_unicas": 0,
            "insertados_ok": 0,
            "fallidos": 0,
            "logs": {"stats": {"total": 0, "exitosos": 0, "fallidos": 0, "advertencias": 0}, "logs": [{"level": "error", "message": f"Error en background task: {str(e)}", "details": {}, "timestamp": datetime.utcnow().isoformat()}]}
        }

@router.post("/", 
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CargaResponse,
    summary="Inicia la carga de datos de una fuente en segundo plano")
async def iniciar_carga_datos(
    request: CargaRequest,
    background_tasks: BackgroundTasks
):
    """
    Inicia la extracción, transformación y carga para una fuente de datos en segundo plano.
    
    **Parámetros:**
    - fuente: El identificador de la fuente ("GAL", "CAT", "VAL")
    
    **Proceso:**
    1. Inicia la carga en segundo plano
    2. Devuelve inmediatamente confirmación de inicio
    3. Cliente debe hacer polling a /api/carga/resultado/{fuente} para obtener el resultado
    
    **Flujo del proceso en background:**
    1. Llama al microservicio extractor correspondiente
    2. El extractor extrae y transforma los datos del archivo fuente
    3. El extractor envía los datos a /api/ingest/
    4. /api/ingest/ detecta duplicados e inserta en BD
    
    **Respuesta (202 ACCEPTED):**
    - Confirmación de que la carga ha sido iniciada
    - El cliente debe hacer polling para obtener el resultado
    
    **Ejemplo de uso:**
    ```bash
    curl -X POST "http://localhost:8000/api/carga/" \\
         -H "Content-Type: application/json" \\
         -d '{"fuente": "GAL"}'
    ```
    """
    # Aceptar fuente
    fuente = request.fuente.upper()

    # 1. Validar que la fuente existe
    if fuente not in EXTRACTOR_MAP:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fuente '{request.fuente}' no reconocida. Fuentes disponibles: {list(EXTRACTOR_MAP.keys())}"
        )
    
    # 2. Marcar que la carga está en proceso (para evitar duplicados)
    if fuente in carga_resultados:
        resultado_previo = carga_resultados[fuente]
        if isinstance(resultado_previo, dict) and resultado_previo.get("status") == "processing":
            # Ya hay una carga en proceso para esta fuente
            return CargaResponse(
                status="processing",
                origen=fuente,
                mensaje=f"Ya hay una carga en proceso para '{fuente}'",
                timestamp=datetime.utcnow().isoformat()
            )
    
    # Marcar como procesando
    carga_resultados[fuente] = {"status": "processing", "timestamp": datetime.utcnow().isoformat()}
        
    # 3. Iniciar carga en segundo plano
    background_tasks.add_task(ejecutar_carga_con_almacenamiento, fuente)
    logger.info(f"Carga para '{fuente}' iniciada en segundo plano")
    
    # 4. Devolver confirmación inmediata
    return CargaResponse(
        status="accepted",
        origen=fuente,
        mensaje=f"Carga para la fuente '{fuente}' iniciada en segundo plano.",
        timestamp=datetime.utcnow().isoformat()
    )

@router.get("/resultado/{fuente}",
    status_code=status.HTTP_200_OK,
    response_model=CargaCompletadaResponse,
    summary="Obtiene el resultado y logs de una carga completada")
async def obtener_resultado_carga(fuente: str):
    """
    Obtiene el resultado completo de una carga incluidos logs detallados.
    
    **Parámetros:**
    - fuente: Identificador de la fuente ("GAL", "CAT", "VAL")
    
    **Respuesta (200 OK) si carga completada:**
    ```json
    {
      "status": "completed",
      "origin": "GAL",
      "estaciones_unicas": 45,
      "insertados_ok": 43,
      "fallidos": 2,
      "logs": {
        "stats": {
          "total": 45,
          "exitosos": 43,
          "fallidos": 2,
          "advertencias": 0
        },
        "logs": [
          {
            "level": "success",
            "message": "Estación cargada",
            "details": {"numero": 1, "nombre": "Estación A Coruña"},
            "timestamp": "2024-12-04T15:30:46.123456Z"
          },
          {
            "level": "error",
            "message": "Error carga registro 5",
            "details": {
              "nombre": "Estación Inválida",
              "razon": "Código postal fuera de rango"
            },
            "timestamp": "2024-12-04T15:30:47.123456Z"
          }
        ]
      }
    }
    ```
    
    **Respuesta (404) si no hay resultado aún:**
    - La carga aún está procesándose
    - Reintentar en unos segundos
    
    **Ejemplo de uso:**
    ```bash
    curl "http://localhost:8000/api/carga/resultado/GAL"
    ```
    """
    fuente = fuente.upper()
    
    if fuente not in carga_resultados:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No hay resultado de carga para '{fuente}'. La carga aún está procesándose o no ha sido iniciada."
        )
    
    resultado = carga_resultados[fuente]
    
    # Si aún está procesando, devolver 404 para que el cliente siga haciendo polling
    if isinstance(resultado, dict) and resultado.get("status") == "processing":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carga para '{fuente}' aún en proceso. Reintentar en 1 segundo."
        )
    
    logger.info(f"Resultado de carga consultado para {fuente}: {resultado.get('status')}")
    return resultado

@router.delete("/limpiar-todo",
    status_code=status.HTTP_200_OK,
    summary="[DEV] Borra TODOS los datos de las tablas (TRUNCATE)")
async def limpiar_base_de_datos():
    """
    **¡Peligro!** Este endpoint vacía completamente las tablas usando `TRUNCATE ... CASCADE`:
    - `Estacion`
    - `Localidad`
    - `Provincia`
    
    Útil para desarrollo y para probar la carga desde cero.
    
    **Respuesta (200 OK):**
    ```json
    {
      "status": "ok",
      "mensaje": "Base de datos limpiada correctamente",
      "deleted": [
        "Tabla 'Estacion': 45 registros eliminados",
        "Tabla 'Localidad': 10 registros eliminados",
        "Tabla 'Provincia': 3 registros eliminados"
      ]
    }
    ```
    
    **Ejemplo de uso:**
    ```bash
    curl -X DELETE "http://localhost:8000/api/carga/limpiar-todo"
    ```
    """
    try:
        # limpiar_todas_las_tablas es una función síncrona que llama a queries de BD
        resultado = limpiar_todas_las_tablas()
        
        # Mejorar respuesta si no tiene la estructura esperada
        if isinstance(resultado, dict):
            if "status" not in resultado:
                resultado["status"] = "ok"
            if "mensaje" not in resultado:
                resultado["mensaje"] = "Base de datos limpiada correctamente"
        
        logger.info(f"Base de datos limpiada: {resultado}")
        return resultado
    except Exception as e:
        logger.error(f"Error al limpiar la base de datos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al limpiar la base de datos: {str(e)}"
        )
