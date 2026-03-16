# 📘 Contexto del Proyecto: Sistema de Integración de Datos ITV

**Fecha de última actualización:** 2024-05-21
**Estado:** Fase de Desarrollo de Infraestructura (MVP)

---

## 1. Visión General del Proyecto
El objetivo del TFG es rediseñar un sistema monolítico/legacy de recolección de datos de estaciones de ITV para convertirlo en una **arquitectura orientada a eventos, modular y escalable**.

El sistema debe ingerir datos de fuentes heterogéneas (XML Cataluña, JSON Valencia, CSV Galicia), normalizarlos bajo un esquema común y persistirlos para su explotación, minimizando el acoplamiento y permitiendo la fácil adición de nuevas fuentes.

---

## 2. Arquitectura del Sistema

### Diagrama de Flujo
`[Gateway] -> (RabbitMQ: raw_data) -> [Normalizer] -> (RabbitMQ: normalized_data) -> [Persister] -> [PostgreSQL]`

### Componentes Principales
| Servicio | Responsabilidad | Tech Stack | Estado |
| :--- | :--- | :--- | :--- |
| **Gateway** | Ingestión de datos. Recibe HTTP POST, valida origen y publica en cola RAW. | FastAPI, aio-pika | ✅ Operativo |
| **RabbitMQ** | Bus de mensajería. Desacopla la ingestión del procesamiento. | RabbitMQ 3 Management | ✅ Operativo |
| **Normalizer** | **Core**. Consume RAW, aplica estrategias de limpieza y publica NORMALIZED. | Python, Pydantic | 🔄 En desarrollo |
| **Persister** | Escritura. Consume NORMALIZED y realiza Upsert en BBDD. | SQLAlchemy Async | ⏳ Pendiente |
| **PostgreSQL** | Base de datos relacional con extensión PostGIS (futuro). | PostgreSQL 15 | ✅ Operativo |

---

## 3. Decisiones de Diseño (Architecture Decision Records)

### ADR-001: Arquitectura Asíncrona con RabbitMQ
* **Decisión:** Separar productores (Gateway) de consumidores (Normalizer) mediante colas.
* **Por qué:** Permite absorber picos de carga sin bloquear la API de entrada. Aísla fallos: si el normalizador cae, los datos no se pierden, se encolan.

### ADR-002: Patrón Strategy para Normalización
* **Decisión:** El servicio `Normalizer` utiliza una **Factory** que instancia un `Transformer` específico basado en el origen del dato (`source`).
* **Por qué:** Cumple el principio **Open/Closed**. Añadir una nueva comunidad autónoma (ej. Madrid) solo requiere añadir una clase `MadridTransformer` sin tocar el código base del consumidor.

### ADR-003: Contrato de Datos Estricto (Pydantic)
* **Decisión:** Definir un modelo `NormalizedStation` que actúa como interfaz universal entre el Normalizador y el Persister.
* **Por qué:** Garantiza la integridad de datos antes de intentar escribir en la BBDD. Facilita la documentación automática (OpenAPI).

### ADR-004: Límites de Recursos (Docker)
* **Decisión:** Uso de `reservations` (suelo) y `limits` (techo) en Docker Compose.
* **Por qué:** Garantiza determinismo en las pruebas de carga y evita que un servicio sature el host.
    * *Normalizer:* Alta CPU (1.0 core).
    * *Gateway/Persister:* Bajos recursos.

---

## 4. Estructura del Repositorio (Monorepo Backend)

```text
/
├── app/                        # Código fuente compartido o microservicios
│   ├── gateway/                # Servicio de Ingestión
│   ├── normalizer/             # Servicio de Transformación
│   │   └── transformers/       # Implementaciones del Strategy Pattern
│   │       ├── standard/       # Lógica determinista (Regex/Python)
│   │       └── experimental/   # Lógica futura (Fuzzy/AI)
│   ├── persister/              # Servicio de Persistencia
│   └── lib/                    # Librerías compartidas (Modelos, Cliente Rabbit)
├── docs/                       # Documentación y Contexto
├── docker-compose.yml          # Orquestación e Infraestructura
└── ...