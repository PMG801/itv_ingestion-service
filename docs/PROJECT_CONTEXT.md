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
3.  **Normalizer (Worker):** Consume de RabbitMQ -> Detecta Dominio -> Aplica Estrategia de Normalización -> Publica en `exchange: normalized_data`.
4.  **Persister (Worker):** Guarda en PostgreSQL/PostGIS.

# Diseño del Sistema ITV Backend

## Flujo de Datos
1. **Gateway**: Recibe POST en `/ingest/{source}`. Envía el payload RAW a la cola `raw_data_queue`.
2. **Normalizer**: Consume de `raw_data_queue`. Valida contra `NormalizedStation` (Pydantic). Envía a `normalized_data_queue`.
3. **Persister**: Consume de `normalized_data_queue`. Realiza el UPSERT en PostgreSQL.

## Infraestructura (QoS)
Todos los servicios tienen límites definidos en `docker-compose.yml`:
- **Normalizer**: CPU 1.0 (Limit), 0.5 (Reservation) para asegurar rendimiento en transformaciones pesadas.
- **RabbitMQ/Postgres**: Reservas de 256MB RAM para estabilidad.