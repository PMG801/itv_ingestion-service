# Tests Refactorizados - Arquitectura de Microservicios

Este directorio contiene los tests modernos para la arquitectura de microservicios.

## 🧪 Estructura de Tests

```
tests/
├── conftest.py                    # Fixtures compartidas
├── test_valencia_api.py           # Tests de Valencia API
├── test_catalunya_api.py          # Tests de Catalunya API
├── test_galicia_api.py            # Tests de Galicia API
├── test_api_central_ingest.py     # Tests de API Central (ingest)
├── test_common_schemas.py         # Tests de schemas compartidos
├── requirements-test.txt          # Dependencias de testing
└── README.md                      # Este archivo
```

## 🚀 Instalación

### 1. Instalar dependencias de testing

```bash
pip install -r tests/requirements-test.txt
```

O instalar todo incluyendo las dependencias principales:

```bash
pip install -r requirements.txt
pip install -r tests/requirements-test.txt
```

### 2. Configurar variables de entorno

Asegúrate de tener un archivo `.env` en la raíz:

```env
DATABASE_URL="postgresql://user:pass@localhost/testdb"
```

## ▶️ Ejecutar Tests

### Todos los tests

```bash
pytest
```

### Tests específicos

```bash
# Solo tests de Valencia API
pytest tests/test_valencia_api.py

# Solo tests de Catalunya API
pytest tests/test_catalunya_api.py

# Solo tests de Galicia API
pytest tests/test_galicia_api.py

# Solo tests de API Central
pytest tests/test_api_central_ingest.py

# Solo tests de schemas
pytest tests/test_common_schemas.py
```

### Con verbose y detalles

```bash
pytest -v
```

### Con cobertura

```bash
# Generar reporte de cobertura
pytest --cov=app --cov=extractor_services --cov-report=html

# Ver reporte
open htmlcov/index.html  # Mac/Linux
# o
start htmlcov/index.html  # Windows
```

### Tests específicos por clase o función

```bash
# Ejecutar una clase específica
pytest tests/test_valencia_api.py::TestHealthEndpoint

# Ejecutar una función específica
pytest tests/test_valencia_api.py::TestHealthEndpoint::test_health_endpoint_root
```

### Filtrar por markers (si están configurados)

```bash
# Solo tests unitarios
pytest -m unit

# Solo tests de API
pytest -m api

# Excluir tests lentos
pytest -m "not slow"
```

## 📋 Cobertura de Tests

### Valencia API
- ✅ Health check endpoints
- ✅ Extract preview (sin envío a central)
- ✅ Extract full (con envío a central)
- ✅ Transformer logic
- ✅ Geocoding service

### Catalunya API
- ✅ Health check endpoints
- ✅ Extract preview
- ✅ Extract full
- ✅ XML parsing
- ✅ Transformer con normalización catalana

### Galicia API
- ✅ Health check endpoints
- ✅ Extract preview
- ✅ Extract full
- ✅ CSV parsing con delimitadores
- ✅ Transformer con normalización gallega

### API Central (Ingest)
- ✅ Endpoint POST /api/ingest
- ✅ Validación de payload
- ✅ Detección de duplicados
- ✅ Operaciones de base de datos
- ✅ Logging y auditoría
- ✅ Performance con lotes grandes

### Schemas Compartidos
- ✅ EstacionExtraida validation
- ✅ PayloadExtraccion validation
- ✅ IngestResponse
- ✅ Serialización/deserialización

## 🔧 Fixtures Disponibles

En [conftest.py](conftest.py):

- `mock_database_url`: Mock de DATABASE_URL
- `sample_estacion`: Estación de ejemplo válida
- `sample_payload`: Payload completo de extracción
- `mock_central_api_success`: Mock de respuesta de API Central
- `mock_httpx_client`: Mock del cliente HTTP

## 📝 Escribir Nuevos Tests

### Ejemplo de test de endpoint

```python
from fastapi.testclient import TestClient

def test_my_endpoint(client):
    response = client.get("/my-endpoint")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
```

### Ejemplo con mocking

```python
from unittest.mock import patch

def test_with_mock(client):
    with patch('module.function', return_value="mocked"):
        response = client.post("/endpoint")
        assert response.status_code == 200
```

### Ejemplo async

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_function()
    assert result is not None
```

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError"

Asegúrate de que Python puede encontrar los módulos:

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

O ejecuta desde la raíz del proyecto:

```bash
cd /home/pau/source/IEI/ITV_BUSCADOR_BACKEND
pytest
```

### Error: "DATABASE_URL must be set"

Crea un archivo `.env` con la variable DATABASE_URL, aunque uses mocks.

### Error: "No tests collected"

Verifica que:
1. Los archivos empiezan con `test_`
2. Las funciones empiezan con `test_`
3. Estás en el directorio correcto

### Tests fallan por conexión a BD

Los tests usan mocks por defecto. Si necesitas BD real:

```python
# Usa el fixture sin mock
def test_with_real_db():
    # Sin usar mock_db_connection
    pass
```

## 📊 CI/CD

### GitHub Actions ejemplo

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pip install -r tests/requirements-test.txt
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## 📚 Recursos

- [pytest documentation](https://docs.pytest.org/)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html)

---

**Versión**: 2.0.0 (Microservicios)  
**Framework**: pytest 7.4+  
**Última actualización**: Diciembre 2025
