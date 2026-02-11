"""
Router para ingestión de datos desde extractores externos (microservicios).
Recibe JSON estandarizado y procesa la carga en BD.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging

from app.db.load_queries import insertar_estacion, buscar_o_crear_provincia, buscar_o_crear_localidad, obtener_estaciones_existentes
from app.db.log_collector import LogCollector
from extractor_services.common.duplicate_detector import DetectorDuplicados

router = APIRouter(
    prefix="/api/ingest",
    tags=["Ingestión de Datos"]
)

logger = logging.getLogger(__name__)


# ===== SCHEMAS =====

class TipoEstacion(str):
    ESTACION_FIJA = "estacion_fija"
    ESTACION_MOVIL = "estacion_movil"
    OTROS = "otros"


class EstacionExtraida(BaseModel):
    """Modelo de estación recibida de un extractor"""
    nombre: str
    tipo: str = "estacion_fija"
    direccion: Optional[str] = None
    codigo_postal: Optional[str] = None
    localidad: str
    provincia: str
    latitud: float
    longitud: float
    descripcion: Optional[str] = None
    horario: Optional[str] = None
    contacto: Optional[str] = None
    url: Optional[str] = None


class RegistroRechazado(BaseModel):
    """Registro rechazado durante transformación"""
    registro: int
    nombre: Optional[str] = None
    razon: str


class EstadisticasExtraccion(BaseModel):
    """Estadísticas del proceso de extracción"""
    total_raw: int
    transformados: int
    rechazados: int


class PayloadExtraccion(BaseModel):
    """Payload completo enviado por un extractor"""
    source: str = Field(..., description="Identificador de la fuente (VAL, CAT, GAL)")
    timestamp: datetime
    estaciones: List[EstacionExtraida]
    rechazados: List[RegistroRechazado] = []
    stats: EstadisticasExtraccion


class IngestResponse(BaseModel):
    """Respuesta al recibir datos de un extractor"""
    status: str
    source: str
    recibidos: int
    insertados: int
    duplicados_detectados: int = 0
    errores_insercion: int = 0
    mensaje: str
    logs: Optional[dict] = None  # Logs detallados del proceso


# ===== ENDPOINT =====

@router.post("/",
    status_code=status.HTTP_200_OK,
    response_model=IngestResponse,
    summary="Recibe datos de un extractor externo")
async def ingest_data(payload: PayloadExtraccion):
    """
    Recibe datos transformados de un microservicio extractor.
    
    **Proceso:**
    1. Recibe el JSON estandarizado
    2. Detecta duplicados contra la carga actual
    3. Detecta duplicados contra la BD existente
    4. Inserta las estaciones nuevas
    5. Retorna resumen de la operación
    
    **Payload esperado:**
    ```json
    {
      "source": "VAL",
      "timestamp": "2024-12-23T10:30:00Z",
      "estaciones": [...],
      "rechazados": [...],
      "stats": {...}
    }
    ```
    """
    logs = LogCollector()
    fuente = payload.source.upper()
    
    logger.info(f"\n{'='*70}")
    logger.info(f"  📥 INGEST RECIBIDO: {fuente}")
    logger.info(f"{'='*70}")
    logger.info(f"📊 Estaciones recibidas: {len(payload.estaciones)}")
    logger.info(f"❌ Rechazados en transformación: {len(payload.rechazados)}")
    
    logs.info(f"Payload recibido de {fuente}", {
        "estaciones": len(payload.estaciones),
        "rechazados": len(payload.rechazados),
        "timestamp": payload.timestamp.isoformat()
    })
    
    # Registrar rechazados del extractor
    for r in payload.rechazados:
        logs.error(f"Rechazo en extractor - Registro {r.registro}", {
            "nombre": r.nombre,
            "razon": r.razon
        })
    
    if not payload.estaciones:
        logger.warning(f"⚠️ No hay estaciones para procesar")
        return IngestResponse(
            status="empty",
            source=fuente,
            recibidos=0,
            insertados=0,
            duplicados_detectados=0,
            errores_insercion=0,
            mensaje="No se recibieron estaciones para procesar",
            logs=logs.get_summary()
        )
    
    # Convertir estaciones al formato interno
    modelos = []
    for est in payload.estaciones:
        # Buscar o crear provincia y localidad
        fk_prov = buscar_o_crear_provincia(est.provincia)
        fk_loc = None
        if fk_prov and est.localidad:
            fk_loc = buscar_o_crear_localidad(est.localidad, fk_prov)
        
        modelo = {
            "nombre": est.nombre,
            "tipo": est.tipo,
            "direccion": est.direccion,
            "codigo_postal": est.codigo_postal,
            "longitud": est.longitud,
            "latitud": est.latitud,
            "descripcion": est.descripcion,
            "horario": est.horario,
            "contacto": est.contacto,
            "url": est.url,
            "localidad_codigo": fk_loc
        }
        modelos.append(modelo)
    
    logger.info(f"✅ {len(modelos)} estaciones convertidas al formato interno")
    
    # DETECTAR DUPLICADOS EN LA CARGA ACTUAL
    detector = DetectorDuplicados()
    modelos_unicos = []
    duplicados_internos = 0
    
    for modelo in modelos:
        es_duplicado = False
        for modelo_existente in modelos_unicos:
            es_dup, criterio = detector.son_duplicados(modelo, modelo_existente)
            if es_dup:
                es_duplicado = True
                duplicados_internos += 1
                logs.warning(f"Duplicado interno detectado", {
                    "nombre": modelo.get('nombre', 'SIN NOMBRE'),
                    "razon": f"Duplicado con otra estación en la misma carga ({criterio})"
                })
                break
        
        if not es_duplicado:
            modelos_unicos.append(modelo)
    
    if duplicados_internos > 0:
        logger.info(f"🔄 Eliminados {duplicados_internos} duplicados internos en la carga")
    
    # DETECTAR DUPLICADOS CONTRA LA BD
    estaciones_existentes = obtener_estaciones_existentes()
    duplicados_bd = 0
    
    if estaciones_existentes:
        modelos_nuevos = []
        
        for modelo in modelos_unicos:
            es_duplicado_bd = False
            
            for est_existente in estaciones_existentes:
                es_dup, criterio = detector.son_duplicados(modelo, est_existente)
                if es_dup:
                    es_duplicado_bd = True
                    duplicados_bd += 1
                    logs.warning(f"Duplicado en BD detectado", {
                        "nombre": modelo.get('nombre', 'SIN NOMBRE'),
                        "razon": f"Ya existe en la base de datos ({criterio})"
                    })
                    logger.debug(f"   Duplicado BD: '{modelo.get('nombre')}' = '{est_existente.get('nombre')}' ({criterio})")
                    break
            
            if not es_duplicado_bd:
                modelos_nuevos.append(modelo)
        
        modelos_unicos = modelos_nuevos
        
        if duplicados_bd > 0:
            logger.info(f"🔄 Encontrados {duplicados_bd} duplicados contra la BD existente")
    
    total_duplicados = duplicados_internos + duplicados_bd
    
    if not modelos_unicos:
        logger.warning(f"⚠️ Todas las estaciones son duplicadas")
        return IngestResponse(
            status="duplicates",
            source=fuente,
            recibidos=len(payload.estaciones),
            insertados=0,
            duplicados_detectados=total_duplicados,
            errores_insercion=0,
            mensaje=f"Todas las estaciones ya existen (duplicados: {total_duplicados})",
            logs=logs.get_summary()
        )
    
    # INSERTAR EN BD
    logger.info(f"\n💾 Insertando {len(modelos_unicos)} estaciones nuevas...")
    insertados = 0
    errores = 0
    
    for i, modelo in enumerate(modelos_unicos, 1):
        nombre = modelo.get('nombre', 'SIN NOMBRE')
        
        exitoso, mensaje_error = insertar_estacion(modelo)
        
        if exitoso:
            insertados += 1
            logs.success(f"Estación insertada", {"nombre": nombre})
        else:
            errores += 1
            logs.error(f"Error inserción", {"nombre": nombre, "razon": mensaje_error})
            logger.error(f"   ❌ Error insertando: {nombre} - {mensaje_error}")
    
    # Determinar status
    if errores == 0:
        status_result = "success"
    elif insertados > 0:
        status_result = "partial"
    else:
        status_result = "error"
    
    logger.info(f"\n{'='*70}")
    logger.info(f"  ✅ INGEST COMPLETADO: {fuente}")
    logger.info(f"{'='*70}")
    logger.info(f"  📊 Recibidas:    {len(payload.estaciones)}")
    logger.info(f"  ✅ Insertadas:   {insertados}")
    logger.info(f"  🔄 Duplicados:   {total_duplicados}")
    logger.info(f"  ❌ Errores:      {errores}")
    logger.info(f"{'='*70}\n")
    
    return IngestResponse(
        status=status_result,
        source=fuente,
        recibidos=len(payload.estaciones),
        insertados=insertados,
        duplicados_detectados=total_duplicados,
        errores_insercion=errores,
        mensaje=f"Carga completada: {insertados} insertadas, {total_duplicados} duplicados, {errores} errores",
        logs=logs.get_summary()
    )


@router.get("/health")
async def health_check():
    """Endpoint de health check para verificar disponibilidad"""
    return {"status": "healthy", "service": "ingest"}
