# Reglas de Desarrollo (Coding Standards)

## 1. Tipado Estricto
Todo el código nuevo debe tener Type Hints de Python.
* ✅ `def process_data(payload: dict) -> ITVStation:`
* ❌ `def process_data(payload):`

## 2. Manejo de Errores
* Nunca hacer un `try/except Exception: pass` silencioso.
* En los Workers de RabbitMQ: Si un mensaje falla, debe ir a una **Dead Letter Queue (DLQ)** o loguear el error con el `message_id` para trazabilidad. No crashear el worker completo.

## 3. Configuración
* No hardcodear credenciales ni URLs. Usar `pydantic-settings` o variables de entorno (`os.getenv`).

## 4. Testing
* Usar `pytest` y `pytest-asyncio`.
* Separar tests unitarios (rápidos) de tests de integración (que requieren Docker levantado).