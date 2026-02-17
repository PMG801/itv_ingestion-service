# Contratos de Datos y Esquemas

El sistema utiliza **Pydantic v2** para validación estricta.

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

# Contrato Universal de Datos (NormalizedStation)

Cualquier dato procesado debe cumplir este esquema de Pydantic:

| Campo | Tipo | Restricción |
| :--- | :--- | :--- |
| `station_id` | str | Prefijo fuente (ej: CAT_) |
| `latitude` | float | range(-90, 90) |
| `longitude` | float | range(-180, 180) |
| `province` | str | Siempre en MAYÚSCULAS |

**Validación Estricta:** Si un campo obligatorio falta, el registro se descarta y se loguea (Fase 1).