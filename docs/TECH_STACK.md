# Stack Tecnológico y Librerías

## Core Stack
* **Lenguaje:** Python 3.10+
* **Web Framework:** FastAPI (Solo para el Gateway y Healthchecks).
* **Async IO:** Uso estricto de `asyncio` y `await`. No usar funciones bloqueantes en el flujo principal.

## Infraestructura & Datos
* **Mensajería:** RabbitMQ.
    * Lib: `aio_pika` (Asíncrono).
* **Base de Datos:** PostgreSQL 15 + PostGIS.
    * Driver: `asyncpg`.
    * ORM/Query Builder: `SQLAlchemy` 2.0 (Async Session).
* **Validación:** Pydantic v2.

## Entorno
* **Docker:** Todo corre bajo `docker-compose`.
* **Recursos:** El código debe ser eficiente en memoria (Limitación de Hardware: 4GB RAM total). Evitar cargar datasets completos en memoria; usar streams o generadores si es posible. 