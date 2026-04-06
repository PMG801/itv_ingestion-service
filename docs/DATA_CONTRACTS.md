# Contratos de Datos y Esquemas

El sistema utiliza **Pydantic v2** para validación estricta.

## Estado actual del contrato (implementación vigente)

El flujo actual usa tres tipos de mensajes en RabbitMQ:
- `raw_data.itv_stations`: entrada cruda desde Gateway.
- `normalized_data.itv_stations`: salida válida tras normalización.
- `rejected_data.itv_stations`: descartes funcionales para trazabilidad y reintento futuro.

## 1. El "Mensaje Universal" (RabbitMQ Envelope)
Cualquier dato que entre al sistema, sea cual sea su origen, debe viajar dentro de esta estructura JSON por las colas.

```json
{
  "header": {
    "message_id": "uuid-v4",
    "timestamp": "iso-8601",
    "domain": "itv_stations",       // Routing Key
    "source_system": "catalunya_api",
    "content_type": "application/xml" // o json, csv
  },
  "payload": {
    "raw_content": "BASE64_STRING_OR_RAW_JSON_OBJECT"
  }
}
```

En la implementación actual del Gateway/Normalizer, la envoltura cruda equivalente contiene:
- `message_id`
- `source`
- `payload`
- `format`
- `ingested_at`

# Contrato Universal de Datos (NormalizedStation)

Cualquier dato procesado debe cumplir este esquema de Pydantic:

| Campo | Tipo | Restricción |
| :--- | :--- | :--- |
| `station_id` | str | Prefijo fuente (ej: CAT_) |
| `latitude` | float | range(-90, 90) |
| `longitude` | float | range(-180, 180) |
| `province` | str | Siempre en MAYÚSCULAS |

**Validación Estricta:** Si un campo obligatorio falta, el registro se descarta y se loguea (Fase 1).

## 2. Contrato de trazabilidad para descartes (`rejected_data`)

Cuando una estación o un mensaje completo no supera normalización, se publica el siguiente evento:

```json
{
  "message_id": "uuid-v4",
  "source": "valencia",
  "format": "json",
  "reason": "missing_raw_id",
  "rejection_level": "station",
  "raw_payload": {
    "nombre": "ITV inválida"
  },
  "rejected_at": "2026-03-19T12:34:56Z"
}
```

### Semántica de campos
- `reason`: motivo técnico/funcional del descarte (machine-readable).
- `rejection_level`:
  - `station`: descarte de un registro concreto.
  - `message`: el mensaje completo no produjo ninguna estación válida.
- `raw_payload`: fragmento crudo para análisis y trazabilidad (sin transformación).

## 3. Trazabilidad operacional

- **Trazabilidad funcional:** `rejected_data.itv_stations` evita pérdida silenciosa de datos filtrados.
- **Trazabilidad técnica:** DLQ para errores de procesamiento/mensajería:
  - `dlq.raw_data.itv_stations`
  - `dlq.normalized_data.itv_stations`
  - `dlq.rejected_data.itv_stations`