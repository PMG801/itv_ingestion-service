# Contexto del Proyecto: Motor de Ingesta y Normalización Universal

## Objetivo Principal
Desarrollar un sistema backend de alto rendimiento (TFG de Ingeniería) diseñado para la **ingesta, normalización y persistencia de datos heterogéneos**.
Aunque el caso de uso actual es **Estaciones de ITV**, el sistema debe ser **agnóstico al dominio**.

## Principios de Arquitectura
1.  **Desacoplamiento Total:** La ingesta (Gateway) no conoce la lógica de negocio. Solo enruta mensajes.
2.  **Arquitectura dirigida por eventos (EDA):** Comunicación asíncrona mediante RabbitMQ.
3.  **Configuración sobre Código:** La adaptación a nuevas fuentes de datos debe priorizar configuración (YAML/JSON) o plugins ligeros sobre reescritura del núcleo.
4.  **Enfoque "Engineering-First":** Priorizamos la mantenibilidad, extensibilidad y métricas sobre la simple funcionalidad.

## Flujo de Datos (High Level)
1.  **Source:** API Externa / Archivo (XML, JSON, CSV).
2.  **Gateway (Ingestion Service):** Recibe datos -> Empaqueta en "Mensaje Universal" -> Publica en RabbitMQ (`exchange: raw_data`).
3.  **Normalizer (Worker):** Consume de RabbitMQ -> Detecta Dominio -> Aplica Estrategia de Normalización -> Publica válidos en `exchange: normalized_data` y filtrados en `exchange: rejected_data`.
4.  **Persister (Worker):** Guarda en PostgreSQL/PostGIS.

## Estado actual de trazabilidad (Marzo 2026)

### 1) Trazabilidad de mensaje end-to-end
- El Gateway genera `message_id` único por petición de ingesta.
- Ese `message_id` viaja por el pipeline y permite correlación en logs y workers.
- El Persister registra resultado en `itv.ingestion_log` con estado `success`/`failed`.

### 2) Trazabilidad de datos válidos
- Los registros normalizados se publican en `normalized_data.itv_stations`.
- El Persister hace UPSERT por `(fuente_origen, id_en_fuente)` para evitar duplicados.

### 3) Trazabilidad de datos filtrados
- El Normalizer ya no descarta silenciosamente:
	- Si una estación no cumple reglas/validación, se publica un evento de rechazo.
	- Si un mensaje completo no produce estaciones válidas, también se publica rechazo.
- Destino: `exchange rejected_data` -> `queue rejected_data.itv_stations`.
- Contrato mínimo de rechazo: `message_id`, `source`, `format`, `reason`, `rejection_level`, `raw_payload`, `rejected_at`.
- En esta fase no existe consumidor de reintentos para esa cola: se retiene para trazabilidad y análisis futuro.

### 4) Errores técnicos de mensajería
- Se mantiene DLX/DLQ para fallos técnicos de consumo/procesamiento:
	- `dlq.raw_data.itv_stations`
	- `dlq.normalized_data.itv_stations`
	- `dlq.rejected_data.itv_stations`

# Diseño del Sistema ITV Backend

## Flujo de Datos
1. **Gateway**: Recibe POST en `/ingest/{source}`. Publica en `raw_data.itv_stations`.
2. **Normalizer**: Consume `raw_data.itv_stations`.
	- Válidos -> `normalized_data.itv_stations`
	- Filtrados -> `rejected_data.itv_stations`
3. **Persister**: Consume `normalized_data.itv_stations`. Realiza UPSERT en PostgreSQL y log de ingestión.

## Infraestructura (QoS)
Todos los servicios tienen límites definidos en `docker-compose.yml`:
- **Normalizer**: CPU 1.0 (Limit), 0.5 (Reservation) para asegurar rendimiento en transformaciones pesadas.
- **RabbitMQ/Postgres**: Reservas de 256MB RAM para estabilidad.

## Evolución LLM y Cache (Abril 2026)

### 1) Multi-provider LLM
- El sistema ya no depende de un único proveedor.
- Se introdujo una arquitectura plugin con `BaseLLMClient` y factoría de cliente.
- Proveedores soportados actualmente:
	- `groq`
	- `azure_openai`
	- `github_models` (GitHub Models / Microsoft Foundry)
- Selección por configuración (`LLM_PROVIDER`) sin cambios en la lógica de negocio.

Notas de autenticación:
- `github_models` requiere `GITHUB_TOKEN` con permisos `models:read`.

### 2) Cache de reglas por tipo de provincia
- Se añade `itv.llm_mapping_rules` para persistir reglas de mapeo semántico.
- Clave de reutilización: `(source_system, province_type)`.
- Política de versionado: una única regla activa por clave; al generar una nueva, la anterior se desactiva.
- Beneficio esperado: reducir llamadas repetidas al LLM y estabilizar latencia/coste.

### 3) Estrategias de normalización aisladas
- Se mantienen separadas las estrategias:
	- RULES
	- FUZZY
	- LLM
- Objetivo: comparar resultados y métricas sin contaminación entre métodos.
- Esto habilita conclusiones experimentales trazables para el TFG.

### 4) Operación manual de invalidación
- Nuevo endpoint de mantenimiento:
	- `DELETE /api/v1/monitoring/llm-rules/{source_system}/{province_type}`
- Uso: invalidar regla activa para forzar regeneración en el siguiente batch.
- Escenario típico: cambio de formato en origen o ajuste de prompt/modelo.