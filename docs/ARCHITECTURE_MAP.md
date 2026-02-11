# Mapa de Arquitectura y Estructura de Directorios

El proyecto sigue una estructura modular estricta. NO colocar lógica de negocio en la raíz ni mezclar dominios.

## Estructura de Carpetas

```text
/itv_data_engine
│
├── /apps                  # Puntos de entrada ejecutables (Microservicios lógicos)
│   ├── /gateway           # FastAPI: Solo recibe datos y los manda a RabbitMQ.
│   ├── /normalizer        # Worker: Procesa y transforma datos.
│   └── /persister         # Worker: Guarda en BD.
│
├── /core                  # Lógica APLICABLE A CUALQUIER DOMINIO (No ITV específica)
│   ├── /messaging         # Wrappers de aio-pika para RabbitMQ.
│   ├── /database          # Conexión asíncrona a Postgres.
│   └── /logging           # Configuración de logs estructurados.
│
├── /domain                # Lógica Específica de Negocio
│   ├── /itv_stations      # Caso de uso: ITV
│   │   ├── models.py      # Pydantic Schemas (Output final).
│   │   ├── mappers.py     # Lógica de transformación (Input -> Output).
│   │   └── rules.py       # Validaciones específicas (ej. coordenadas en España).
│   │
│   └── /traffic_lights    # (Futuro) Otro dominio.
│
├── /providers             # Adaptadores de Fuentes Externas
│   ├── /catalunya_api     # Lógica para leer el XML de Cataluña.
│   └── /valencia_api      # Lógica para leer el JSON de Valencia.
│
└── /docs                  # Contexto para desarrollo e IA.