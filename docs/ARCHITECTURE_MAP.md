# Mapa de Arquitectura y Estructura de Directorios

El proyecto sigue una estructura modular estricta. NO colocar lógica de negocio en la raíz ni mezclar dominios.

## Estructura de Carpetas

```text
/itv_data_engine
│
├── /apps                  # Puntos de entrada ejecutables (Microservicios lógicos)
│   ├── /gateway           # FastAPI: Solo recibe datos y los manda a RabbitMQ.
│   ├── /normalizer        # Worker: Procesa, normaliza y clasifica válidos/filtrados.
│   └── /persister         # Worker: Guarda en BD.
│
├── /core                  # Lógica APLICABLE A CUALQUIER DOMINIO (No ITV específica)
│   ├── /messaging         # Wrappers de aio-pika para RabbitMQ.
│   ├── /database          # Conexión asíncrona a Postgres.
│   └── /logging           # Configuración de logs estructurados.
│
├── /domain                # Lógica Específica de Negocio
│   ├── /itv_stations      # Caso de uso: ITV
│   │   ├── models.py      # Modelos ORM.
│   │   ├── schemas.py     # Contratos normalizados.
│   │   ├── mappers.py     # Lógica de transformación (Input -> Output).
│   │   ├── rules.py       # Validaciones específicas (ej. coordenadas en España).
│   │   └── transformers/  # Estrategias por fuente.
│   │
│   └── /traffic_lights    # (Futuro) Otro dominio.
│
├── /providers             # Adaptadores de Fuentes Externas
│   ├── /catalunya_api     # Lógica para leer el XML de Cataluña.
│   └── /valencia_api      # Lógica para leer el JSON de Valencia.
│
└── /docs                  # Contexto para desarrollo e IA.
```

## Flujo de eventos actual (trazabilidad)

```text
Gateway
  └─(raw_data / itv_stations)─> raw_data.itv_stations
                                 │
                                 ▼
                             Normalizer
                               ├─ válidos ─> (normalized_data / itv_stations) ─> normalized_data.itv_stations ─> Persister
                               └─ filtrados -> (rejected_data / itv_stations) ─> rejected_data.itv_stations

DLX (errores técnicos)
  ├─ dlq.raw_data.itv_stations
  ├─ dlq.normalized_data.itv_stations
  └─ dlq.rejected_data.itv_stations
```

### Nota operativa
- `rejected_data.itv_stations` conserva descartes funcionales del normalizador para trazabilidad.
- Estado actual: sin consumidor de reintento automático (solo retención/inspección).
