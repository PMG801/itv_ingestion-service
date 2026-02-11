# 🚗 ITV Buscador - Backend

> Sistema backend para búsqueda y gestión de estaciones ITV en España con arquitectura de microservicios

## 📚 Índice

1. [Descripción General](#descripción-general)
2. [Arquitectura del Sistema](#arquitectura-del-sistema)
3. [Stack Tecnológico](#stack-tecnológico)
4. [Estructura del Proyecto](#estructura-del-proyecto)
5. [Instalación](#instalación)
6. [Configuración](#configuración)
7. [Ejecución](#ejecución)
8. [API Reference](#api-reference)
9. [Base de Datos](#base-de-datos)

---

## 📝 Descripción General

Este proyecto implementa un sistema backend completo para la gestión y búsqueda de estaciones ITV (Inspección Técnica de Vehículos) en España. El sistema integra datos de múltiples fuentes autonómicas (Galicia, Catalunya, Comunidad Valenciana) en una base de datos centralizada PostgreSQL y proporciona APIs REST para consulta y carga de datos.

### 🎯 Características Principales

- **Búsqueda avanzada** con múltiples filtros (localidad, provincia, código postal, tipo)
- **Arquitectura de microservicios** independientes para cada fuente de datos
- **Geocodificación automática** de direcciones usando Nominatim (OpenStreetMap)
- **Detección de duplicados** inteligente antes de insertar registros
- **Normalización de datos** desde formatos heterogéneos (JSON, XML, CSV)
- **API REST documentada** con Swagger/OpenAPI
- **Sistema de logging** detallado para auditoría y debugging

---

## 🏛️ Arquitectura del Sistema

El sistema está compuesto por **dos APIs especializadas** y **tres microservicios extractores independientes**:

```
┌──────────────────────────────────────────────────────────────────────┐
│                            FRONTEND                                  │
└──────────────────────┬───────────────────────┬───────────────────────┘
                       │                       │
    GET /api/estaciones│                       │POST /api/carga
    GET /api/provincias│                       │GET /api/carga/resultado
                       ▼                       ▼
┌─────────────────────────────┐  ┌─────────────────────────────────────┐
│   API DE BÚSQUEDA           │  │          API DE CARGA               │
│   (Puerto 8004)             │  │          (Puerto 8000)              │
│                             │  │                                     │
│  📤 ENDPOINTS               │  │  📤 ENDPOINTS                       │
│  • GET /api/estaciones      │  │  • POST /api/carga/ - Iniciar       │
│  • GET /api/provincias      │  │  • GET /api/carga/resultado/{f}     │
│                             │  │  • DELETE /api/carga/limpiar-todo   │
│  → Lee datos de PostgreSQL  │  │  • POST /api/ingest/ - Recibir      │
│  → Devuelve JSON            │  │                                     │
└────────────┬────────────────┘  └───────────────┬─────────────────────┘
             │                                   │
             │       ┌───────────────────┐       │ POST /api/ingest
             └──────▶│    PostgreSQL     │◀──────┘
                     │  (BBDD Transf.)   │
                     └───────────────────┘
                                ▲
                                │ POST /api/ingest (JSON estandarizado)
             ┌──────────────────┼──────────────────┐
             │                  │                  │
    ┌────────┴─────────┐ ┌─────┴────────┐ ┌───────┴────────┐
    │  Valencia API    │ │Catalunya API │ │  Galicia API   │
    │  (Puerto 8001)   │ │(Puerto 8002) │ │ (Puerto 8003)  │
    │                  │ │              │ │                │
    │  📄 .json        │ │  📄 .xml     │ │  📄 .csv       │
    │       ↓          │ │       ↓      │ │      ↓         │
    │  🔧 Extrae       │ │  🔧 Extrae   │ │ 🔧 Extrae      │
    │  🔄 Transforma   │ │  🔄 Transf.  │ │ 🔄 Transforma  │
    │  📤 Envía JSON   │ │  📤 Envía    │ │ 📤 Envía JSON  │
    └──────────────────┘ └──────────────┘ └────────────────┘
```

### 🎯 Componentes del Sistema

#### 1. **API de Búsqueda** (Puerto 8004)
- **Responsabilidad**: Servir datos al frontend
- **Endpoints**:
  - `GET /api/estaciones` - Búsqueda de estaciones con filtros
  - `GET /api/provincias` - Listado de provincias disponibles
- **Características**: Solo lectura, optimizada para consultas rápidas

#### 2. **API de Carga** (Puerto 8000)
- **Responsabilidad**: Gestión de ingesta de datos
- **Endpoints**:
  - `POST /api/carga/` - Inicia proceso de carga desde una fuente
  - `GET /api/carga/resultado/{fuente}` - Consulta resultado de carga
  - `POST /api/ingest/` - Recibe datos desde extractores
  - `DELETE /api/carga/limpiar-todo` - Limpia completamente la BD
- **Características**: Procesos en segundo plano, logging detallado

#### 3. **Microservicios Extractores** (Puertos 8001-8003)
- **Valencia** (8001): Procesa archivos JSON
- **Catalunya** (8002): Procesa archivos XML con XSLT
- **Galicia** (8003): Procesa archivos CSV
- **Responsabilidad común**:
  - Lectura de archivos fuente
  - Normalización al esquema estándar
  - Geocodificación de direcciones
  - Envío a API de Carga

---

## 💻 Stack Tecnológico

| Tecnología | Versión | Propósito |
|-------------|---------|-----------|
| **Python** | 3.11+ | Lenguaje principal |
| **FastAPI** | Latest | Framework web asíncrono |
| **PostgreSQL** | 14+ | Base de datos relacional |
| **psycopg** | 3.x | Driver PostgreSQL |
| **Pydantic** | 2.x | Validación de datos y settings |
| **pandas** | Latest | Procesamiento de datos (CSV/XML) |
| **geopy** | Latest | Geocodificación (Nominatim) |
| **python-dotenv** | Latest | Gestión de variables de entorno |
| **uvicorn** | Latest | Servidor ASGI |

---

## 📚 Estructura del Proyecto

```
ITV_BUSCADOR_BACKEND/
├── app/                          # 🎯 API Central
│   ├── main.py                  # Punto de entrada FastAPI
│   ├── config.py                # Configuración (.env)
│   │
│   ├── busqueda/                # Módulo de búsqueda
│   │   ├── main.py            # API de búsqueda independiente
│   │   └── routers/
│   │       ├── stations_router.py  # GET /api/estaciones
│   │       └── geo_router.py      # GET /api/provincias
│   │
│   ├── carga/                   # Módulo de carga
│   │   ├── main.py            # API de carga independiente
│   │   └── routers/
│   │       ├── load_router.py     # POST /api/carga
│   │       └── ingest_router.py   # POST /api/ingest
│   │
│   ├── db/                      # Capa de base de datos
│   │   ├── connection.py       # Pool de conexiones
│   │   ├── search_queries.py   # Queries de búsqueda
│   │   ├── load_queries.py     # Queries de inserción
│   │   └── log_collector.py    # Logs de carga
│   │
│   ├── schemas/                 # Modelos Pydantic
│   │   ├── station.py         # Esquema de estación
│   │   └── location.py        # Esquemas geográficos
│   │
│   └── services/                # Lógica de negocio
│       └── load_service.py     # Servicio de carga
│
├── extractor_services/        # 🔧 Microservicios extractores
│   ├── valencia_api/          # Extractor Valencia (JSON)
│   │   ├── main.py
│   │   ├── extractor.py
│   │   └── transformer.py
│   │
│   ├── catalunya_api/         # Extractor Catalunya (XML)
│   │   ├── main.py
│   │   ├── extractor.py
│   │   └── transformer.py
│   │
│   ├── galicia_api/           # Extractor Galicia (CSV)
│   │   ├── main.py
│   │   ├── extractor.py
│   │   └── transformer.py
│   │
│   ├── common/                # Código compartido
│   │   ├── schemas.py         # Esquemas comunes
│   │   ├── client.py          # Cliente HTTP
│   │   ├── normalizers.py     # Normalización de datos
│   │   ├── duplicate_detector.py  # Detección duplicados
│   │   └── geocoding.py       # Geocodificación
│   │
│   └── data/                  # Archivos fuente
│       ├── estaciones_cv.json
│       ├── estaciones_cat.xml
│       └── estaciones_gal.csv
│
├── tests/                     # 🧪 Tests
│   ├── test_api_central_ingest.py
│   ├── test_catalunya_api.py
│   ├── test_galicia_api.py
│   ├── test_valencia_api.py
│   └── test_common_schemas.py
│
├── logs/                      # 📄 Logs del sistema
├── start_services.py           # 🚀 Script de arranque
├── requirements.txt            # Dependencias
├── .env                        # Variables de entorno
└── README.md                   # Este archivo
```

---

## 🛠️ Instalación

### Requisitos Previos

- Python 3.11 o superior
- PostgreSQL 14+ (o acceso a Supabase)
- pip (gestor de paquetes de Python)
- Git

### Paso 1: Clonar el repositorio

```bash
git clone <url-del-repositorio>
cd ITV_BUSCADOR_BACKEND
```

### Paso 2: Crear entorno virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Linux/Mac:
source venv/bin/activate
# En Windows:
venv\Scripts\activate
```

### Paso 3: Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 4: Verificar instalación

```bash
python -c "import fastapi, psycopg, pandas; print('✅ Todas las dependencias instaladas correctamente')"
```

---

## ⚙️ Configuración

### Variables de Entorno

Crear un archivo `.env` en la raíz del proyecto:

```env
# Conexión a PostgreSQL (Supabase o local)
DATABASE_URL=postgresql://usuario:contraseña@host:puerto/nombre_db

# Ejemplo con Supabase:
# DATABASE_URL=postgresql://postgres.xxxxx:password@aws-0-eu-west-1.pooler.supabase.com:5432/postgres

# Ejemplo local:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/itv_db
```

### Archivos de Datos Fuente

Los archivos deben estar ubicados en `extractor_services/data/`:

- ✅ `estaciones_cv.json` (Comunidad Valenciana)
- ✅ `estaciones_cat.xml` (Catalunya)
- ✅ `estaciones_gal.csv` (Galicia)

### Esquema de Base de Datos

El sistema requiere las siguientes tablas en PostgreSQL:

```sql
-- Tabla de provincias
CREATE TABLE provincia (
    codigo SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL
);

-- Tabla de localidades
CREATE TABLE localidad (
    codigo SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    provincia_codigo INTEGER REFERENCES provincia(codigo),
    UNIQUE(nombre, provincia_codigo)
);

-- Tabla de estaciones
CREATE TABLE estacion (
    cod_estacion SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    tipo VARCHAR(50),  -- estacion_fija, estacion_movil, otros
    direccion TEXT,
    codigo_postal VARCHAR(10),
    latitud DECIMAL(10, 8),
    longitud DECIMAL(11, 8),
    descripcion TEXT,
    horario TEXT,
    contacto VARCHAR(255),
    url TEXT,
    localidad_codigo INTEGER REFERENCES localidad(codigo)
);

-- Índices para optimizar búsquedas
CREATE INDEX idx_estacion_localidad ON estacion(localidad_codigo);
CREATE INDEX idx_estacion_tipo ON estacion(tipo);
CREATE INDEX idx_estacion_cp ON estacion(codigo_postal);
CREATE INDEX idx_localidad_provincia ON localidad(provincia_codigo);
```

---

## 🚀 Ejecución

### Opción 1: Script de Arranque Automático (Recomendado)

El proyecto incluye un script que levanta todos los servicios automáticamente:

```bash
python start_services.py
```

Este script:
- ✅ Levanta la API Central (puerto 8000)
- ✅ Levanta los tres microservicios extractores (puertos 8001-8003)
- ✅ Muestra logs consolidados en tiempo real
- ✅ Maneja el cierre limpio de todos los servicios con Ctrl+C

### Opción 2: Arranque Manual

Si prefieres control total, abre **4 terminales**:

#### Terminal 1: API Central (Puerto 8000) - OBLIGATORIO

```bash
cd ITV_BUSCADOR_BACKEND
source venv/bin/activate
uvicorn app.carga.main:app --reload --port 8000
```

✅ **Verificar**: http://localhost:8000/docs

#### Terminal 2: API Central (Puerto 8000) - OBLIGATORIO

```bash
cd ITV_BUSCADOR_BACKEND/
source venv/bin/activate
uvicorn app.carga.busqueda:app --reload --port 8004
```

✅ **Verificar**: http://localhost:8004/docs

#### Terminal 3: Extractor Valencia (Puerto 8001) - OPCIONAL

```bash
cd ITV_BUSCADOR_BACKEND/extractor_services/valencia_api
source ../../venv/bin/activate
PYTHONPATH=.. uvicorn main:app --reload --port 8001
```

✅ **Verificar**: http://localhost:8001/docs

#### Terminal 4: Extractor Catalunya (Puerto 8002) - OPCIONAL

```bash
cd ITV_BUSCADOR_BACKEND/extractor_services/catalunya_api
source ../../venv/bin/activate
PYTHONPATH=.. uvicorn main:app --reload --port 8002
```

✅ **Verificar**: http://localhost:8002/docs

#### Terminal 5: Extractor Galicia (Puerto 8003) - OPCIONAL

```bash
cd ITV_BUSCADOR_BACKEND/extractor_services/galicia_api
source ../../venv/bin/activate
PYTHONPATH=.. uvicorn main:app --reload --port 8003
```

✅ **Verificar**: http://localhost:8003/docs

### ⚠️ Notas Importantes

- La **API Central (puerto 8000) es OBLIGATORIA** - el frontend la necesita
- Los **extractores (8001-8003) son OPCIONALES** - solo para cargar/actualizar datos
- Si ya tienes datos en la BD, el frontend funciona solo con la API Central

---

## 📚 API Reference

### API de Búsqueda (Puerto 8004 o ruta /api/)

#### GET /api/estaciones
Busca estaciones con filtros opcionales.

**Parámetros de Query**:
- `localidad` (string, opcional): Filtra por nombre de localidad (parcial, case-insensitive)
- `codigo_postal` (string, opcional): Filtra por código postal (prefijo o exacto)
- `provincia` (string, opcional): Filtra por nombre de provincia (parcial, case-insensitive)
- `tipo` (string, opcional): Filtra por tipo ("fija", "movil", "otros")

**Ejemplo**:
```bash
curl "http://localhost:8000/api/estaciones?provincia=Madrid&tipo=fija"
```

**Respuesta**:
```json
[
  {
    "nombre": "ITV Madrid Norte",
    "direccion": "Calle Example 123",
    "localidad": "Madrid",
    "codigo_postal": "28001",
    "provincia": "Madrid",
    "descripcion": "Estación ITV",
    "tipo": "estacion_fija",
    "latitud": 40.4168,
    "longitud": -3.7038
  }
]
```

#### GET /api/provincias
Obtiene lista de todas las provincias disponibles.

**Respuesta**:
```json
[
  { "codigo": 1, "nombre": "A Coruña" },
  { "codigo": 2, "nombre": "Barcelona" },
  { "codigo": 3, "nombre": "Madrid" }
]
```

### API de Carga (Puerto 8000)

#### POST /api/carga/
Inicia proceso de carga desde una fuente específica.

**Body**:
```json
{
  "fuente": "GAL"  // GAL, CAT, o VAL
}
```

**Respuesta**:
```json
{
  "status": "accepted",
  "origen": "GAL",
  "mensaje": "Carga iniciada en segundo plano",
  "timestamp": "2024-12-04T15:30:45.123456Z"
}
```

#### GET /api/carga/resultado/{fuente}
Consulta el resultado de una carga previamente iniciada.

**Parámetros**:
- `fuente` (path): Código de fuente (GAL, CAT, VAL)

**Respuesta**:
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
    "logs": []
  }
}
```

#### DELETE /api/carga/limpiar-todo
Elimina TODOS los datos de la base de datos (provincias, localidades, estaciones).

**Respuesta**:
```json
{
  "status": "success",
  "message": "Base de datos limpiada completamente"
}
```

#### POST /api/ingest/
Endpoint interno para que los extractores envíen datos normalizados.

### Microservicios Extractores (Puertos 8001-8003)

#### POST /extract
Inicia extracción, transformación y envío a API Central.

**Respuesta**:
```json
{
  "status": "success",
  "source": "VAL",
  "extraidos": 49,
  "enviado_a_central": true,
  "respuesta_central": {
    "status": "success",
    "insertados": 47,
    "duplicados_detectados": 2
  }
}
```

#### POST /extract/preview
Muestra datos extraídos SIN enviar a la base de datos (para testing).

---

## 📊 Base de Datos

### Modelo Entidad-Relación

```
PROVINCIA (1) ----< (N) LOCALIDAD (1) ----< (N) ESTACION
    |                       |                       |
    codigo                  codigo                  cod_estacion
    nombre                  nombre                  nombre
                            provincia_codigo        tipo
                                                    direccion
                                                    codigo_postal
                                                    latitud
                                                    longitud
                                                    localidad_codigo
```

---
