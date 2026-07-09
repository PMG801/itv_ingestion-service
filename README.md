# ITV Data Engine - Motor de Ingesta y Normalización Universal

Sistema backend de alto rendimiento para la ingesta, normalización y persistencia de datos heterogéneos.

## 🏗️ Arquitectura

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐      ┌──────────────┐
│   Gateway   │─────▶│   RabbitMQ   │─────▶│ Normalizer  │─────▶│  PostgreSQL  │
│  (FastAPI)  │      │ (raw_data)   │      │  (Worker)   │      │   + PostGIS  │
└─────────────┘      └──────────────┘      └─────────────┘      └──────────────┘
                                                  │
                                                  ▼
                                            ┌──────────────┐
                                            │   RabbitMQ   │
                                            │(normalized)  │
                                            └──────────────┘
                                                  │
                                                  ▼
                                            ┌─────────────┐
                                            │  Persister  │
                                            │  (Worker)   │
                                            └─────────────┘
```

## 📁 Estructura del Proyecto

```
/itv-ingestion-service
├── /apps                  # Microservicios ejecutables
│   ├── /gateway          # FastAPI - Punto de entrada
│   ├── /normalizer       # Worker de transformación
│   └── /persister        # Worker de persistencia
├── /core                  # Lógica agnóstica al dominio
│   ├── /messaging        # Wrappers de RabbitMQ
│   ├── /database         # Conexión PostgreSQL
│   └── /logging          # Configuración de logs
├── /domain               # Lógica de negocio
│   └── /itv_stations     # Dominio ITV
├── /infra                # Configuración de infraestructura
│   ├── /rabbitmq         # Definiciones y configuración
│   └── /postgres         # Scripts de inicialización
└── /docs                 # Documentación del proyecto
```

## 🚀 Quick Start

### Prerrequisitos
- Docker & Docker Compose
- Python 3.11+ (para desarrollo local)
- PDM (Python Dependency Manager): `pip install pdm`

### 1. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 2. Levantar infraestructura completa
```bash
# Todo en uno (infraestructura + aplicaciones)
docker-compose up --build

# O por separado:
# 1. Solo infraestructura (RabbitMQ + PostgreSQL)
docker-compose -f infra/docker-compose.infrastructure.yml up -d

# 2. Aplicaciones
docker-compose -f infra/docker-compose.apps.yml up --build
```

### 3. Verificar servicios
- **Gateway API:** http://localhost:8000/docs
- **RabbitMQ Management:** http://localhost:15672 (admin/admin123)
- **PostgreSQL:** localhost:5432

## 🧪 Desarrollo Local

```bash
# Instalar PDM
pip install pdm

# Instalar dependencias
pdm install

# Instalar dependencias de desarrollo
pdm install -d

# Ejecutar tests
pdm run test

# Con cobertura
pdm run test-cov

# Formatear código
pdm run format

# Linting
pdm run lint

# Type checking
pdm run type-check
```

## 📋 Endpoints Principales

### Gateway (Puerto 8000)
- `GET /health` - Health check
- `POST /api/v1/ingest/{source}` - Encola payload crudo para ingesta asíncrona
- `POST /api/v1/inject/synthetic/{source}` - Inyección de datos sintéticos
- `POST /api/v1/files/upload/{source}` - Carga de archivo (JSON/XML/CSV)
- `GET /api/v1/monitoring/ingest/{message_id}` - Estado de ingesta por mensaje
- `GET /api/v1/monitoring/metrics` - Métricas agregadas (sin métricas de rate)
- `GET /api/v1/stations/all` - Consulta de estaciones persistidas

### Breaking Changes (2026-04)
- Eliminado `POST/GET/DELETE /api/carga/*` (router de compatibilidad legacy).
- Eliminado `GET /api/v1/sources`.
- Eliminados `GET /api/v1/stations/provinces` y `GET /api/provincias`.
- Eliminado `GET /api/v1/monitoring/health-detailed`.
- `POST /api/v1/inject/synthetic/{source}` ya no acepta `error_rate` ni `include_errors`.

## 🔧 Configuración Avanzada

### Escalado de Workers
Edita el archivo `.env`:
```bash
NORMALIZER_REPLICAS=4  # Número de workers normalizadores
PERSISTER_REPLICAS=2   # Número de workers persistidores
```

### Experimento LLM (Groq)

Para ejecutar el experimento de mapeo semántico con LLM, configura en `.env`:

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
LLM_MODEL=llama3-8b-8192
LLM_BATCH_SIZE=5
LLM_TEMPERATURE=0.0
LLM_REQUEST_TIMEOUT_S=30
NORMALIZATION_MODE=LLM
```

Restricciones del experimento:

### Experimento LLM con Múltiples Proveedores

El sistema soporta múltiples proveedores LLM a través de un plugin architecture configurable:

#### Opción 1: Groq (Predeterminado)
```bash
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
LLM_MODEL=llama3-8b-8192
LLM_BATCH_SIZE=5
LLM_TEMPERATURE=0.0
LLM_REQUEST_TIMEOUT_S=30
NORMALIZATION_MODE=LLM
```

Para más detalles de configuración y opciones avanzadas, consulta la sección de entorno en [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md).
curl -X DELETE http://localhost:8000/api/v1/monitoring/llm-rules/{source_system}/{province_type}
```

**Paso 4: Monitorear métricas**
- Acceder a: http://localhost:8000/api/v1/monitoring/metrics
- Verificar: `llm_rule_cache_hit`, `llm_token_usage` (estos cambiarán al cambiar modelo)

### RabbitMQ Exchanges y Queues
- **raw_data:** Datos sin procesar
- **normalized_data:** Datos normalizados
- **rejected_data:** Registros filtrados en normalización (trazabilidad/reintentos futuros)
- **dlx:** Dead Letter Exchange (mensajes fallidos)

Ver configuración completa en `infra/rabbitmq/definitions.json`

## 📚 Documentación

- [Contexto del Proyecto](docs/PROJECT_CONTEXT.md)
- [Mapa de Arquitectura](docs/ARCHITECTURE_MAP.md)
- [Stack Tecnológico](docs/TECH_STACK.md)
- [Reglas de Desarrollo](docs/CODING_RULES.md)
- [Contratos de Datos](docs/DATA_CONTRACTS.md)

## 🛠️ Stack Tecnológico

- **Python 3.11+**
- **FastAPI** - Web framework
- **RabbitMQ** - Message broker (aio-pika)
- **PostgreSQL 15 + PostGIS** - Base de datos geoespacial
- **SQLAlchemy 2.0** - ORM async
- **Pydantic v2** - Validación de datos
- **Docker** - Containerización

## 📝 Licencia

TFG - Ingeniería Informática
