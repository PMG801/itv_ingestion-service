# 🔍 Informe de Tests - Estado Actual

## 📊 Resumen General

```
Total Tests: 66 (sin legacy)
├─ Passed: 20 (30%)
├─ Failed: 23 (35%)
└─ Errors: 23 (35%)
```

**Progreso**: ✅ Tests legacy movidos a `tests/legacy/`

## ✅ Tests Funcionando Correctamente

### test_common_schemas.py
- **Estado**: ✅ 14/14 PASSED (100%)
- **Cobertura**: EstacionExtraida, PayloadExtraccion, IngestResponse, serialización
- **Sin problemas** - Estos tests funcionan perfectamente

### test_api_central_ingest.py
- **Estado**: ⚠️ 3/13 PASSED (23%)
- **Tests OK**: 
  - `test_ingest_invalid_payload_missing_source` ✅
  - `test_validate_required_fields` ✅
  - `test_validate_timestamp_format` ✅
- **Problemas**: Mocks de BD incorrectos (8 errors)

## ❌ Tests con Problemas

### 1. **Tests de APIs de Extractores** (Valencia, Catalunya, Galicia)

#### Problema Principal: Import Errors
```
ModuleNotFoundError: No module named 'extractor'
ModuleNotFoundError: No module named 'transformer'
ModuleNotFoundError: No module named 'geocoding'
```

**Causa**: Los archivos `main.py` de cada API usan imports relativos:
```python
# En valencia_api/main.py:
from extractor import ValenciaExtractorService  # ❌ Import relativo
```

**Solución Requerida**: Los tests necesitan ajustar PYTHONPATH o usar imports absolutos.

#### Problema Secundario: API de Transformers
```
TypeError: CatalunyaTransformer.transform_item() takes 2 positional arguments but 3 were given
```

**Causa**: Los transformers tienen diferentes signatures:
- Test espera: `transform_item(raw_item, index)`
- Real: `transform_item(raw_item)` (sin index)

### 2. **test_api_central_ingest.py**

#### Problema: Mock Incorrecto
```
AttributeError: <module 'app.db.load_queries'> does not have the attribute 'get_connection'
```

**Causa**: El módulo `load_queries.py` no exporta `get_connection`, usa `get_db_connection()` u otra función.

**Impacto**: 8 tests con ERROR

### 3. **Tests Legacy Interfiriendo**

Los tests legacy (`test_extractors_refactor.py`, `test_todos_extractores.py`, etc.) se ejecutan junto con los nuevos y causan:
- Tiempos de ejecución largos
- Errores que oscurecen los resultados
- Confusión en los reportes

## 📊 Desglose por Suite

### ✅ test_common_schemas.py: 14/14 (100%)
- Validación Pydantic funciona perfectamente
- Todos los schemas se validan correctamente

### ⚠️ test_api_central_ingest.py: 3/13 (23%)
- **Passed**: Validación de schemas en endpoints
- **Errores**: Mocks de BD necesitan ajustes

### ❌ test_valencia_api.py: 0/12 (0%)
- **Errores**: 7 import errors, 5 test failures
- **Causa**: `from extractor import ...` no resuelve correctamente

### ❌ test_catalunya_api.py: 0/12 (0%)  
- **Errores**: 7 import errors, 5 test failures
- **Causa**: Similar a Valencia

### ❌ test_galicia_api.py: 3/15 (20%)
- **Passed**: 3 tests básicos funcionan
- **Errores**: 9 import errors, 6 test failures

## 🔧 Soluciones Recomendadas

### Opción 1: Mover Tests Legacy (RECOMENDADO)
```bash
mkdir tests/legacy
mv tests/test_deteccion_duplicados.py tests/legacy/
mv tests/test_duplicados_bd.py tests/legacy/
mv tests/test_extractors_refactor.py tests/legacy/
mv tests/test_integracion_galicia.py tests/legacy/
mv tests/test_logs_mejorados.py tests/legacy/
mv tests/test_todos_extractores.py tests/legacy/
mv tests/test_validacion_codigo_postal.py tests/legacy/
mv tests/verificar_refactorizacion.py tests/legacy/
```

### Opción 2: Ejecutar Solo Tests Nuevos
```bash
# Ejecutar solo tests refactorizados
pytest tests/test_common_schemas.py -v
pytest tests/test_valencia_api.py -v --tb=short
pytest tests/test_catalunya_api.py -v --tb=short
pytest tests/test_galicia_api.py -v --tb=short
pytest tests/test_api_central_ingest.py -v --tb=short
```

### Opción 3: Usar Markers
```python
# En conftest.py agregar marker
pytest_configure = lambda config: config.addinivalue_line(
    "markers", "refactored: Tests refactorizados para microservicios"
)

# En cada test nuevo agregar:
@pytest.mark.refactored

# Ejecutar solo tests refactorizados:
pytest -m refactored
```

## 🐛 Fixes Necesarios

### Fix 1: Fixture mock_db_connection
```python
# En conftest.py cambiar:
@pytest.fixture
def mock_db_connection():
    with patch('app.db.connection.get_db_connection') as mock_conn:  # Ruta correcta
        # ...
```

### Fix 2: PYTHONPATH para Tests de Extractores
```python
# En conftest.py agregar:
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'extractor_services', 'valencia_api'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'extractor_services', 'catalunya_api'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'extractor_services', 'galicia_api'))
```

### Fix 3: Signature de Transformers
```python
# En tests, verificar signature real primero:
def test_transform_valid_station():
    transformer = ValenciaTransformer()
    # Usar signature correcta (sin index)
    result = transformer.transform_item(raw_item)
```

## 📋 Plan de Acción

### ✅ Completado
1. ✅ Tests legacy movidos a `tests/legacy/`
2. ✅ PYTHONPATH configurado en conftest.py

### 🔧 Pendiente
3. ⚠️ **Crítico**: Los tests de extractores requieren que los servicios estén corriendo
   - **Alternativa 1**: Levantar docker-compose antes de tests
   - **Alternativa 2**: Mockear completamente los servicios (más trabajo)
   
4. ⚠️ **Importante**: Corregir fixture `mock_db_connection`
   - Cambiar `get_connection` → `get_db_connection`
   
5. ⚠️ **Importante**: Corregir signatures de transformers en tests
   - Quitar segundo parámetro `index` en llamadas

## 🎯 Objetivo

**Estado Deseado**:
```
tests/
├── conftest.py                    # Fixtures compartidas
├── test_common_schemas.py         # ✅ WORKING
├── test_valencia_api.py           # 🔧 NEEDS PYTHONPATH FIX
## 🎬 Recomendación Final

### Opción A: Tests con Docker (Recomendado para CI/CD)
```bash
# 1. Levantar servicios
cd extractor_services && docker-compose up -d

# 2. Ejecutar tests
cd .. && pytest tests/

# 3. Bajar servicios
cd extractor_services && docker-compose down
```

### Opción B: Tests Unitarios Puros (Más rápido)
Los tests actuales ya están diseñados con mocks, pero necesitan:
- Ajustar imports para trabajar sin servicios corriendo
- Mockear completamente las dependencias internas
- Enfoque en lógica de negocio, no en integración

### Opción C: Separar Tests
```
tests/
├── unit/               # Tests sin dependencias externas
│   ├── test_common_schemas.py  ✅ WORKING
│   └── test_transformers.py    🔧 TODO
│
├── integration/        # Tests que requieren servicios
│   ├── test_valencia_api.py
│   ├── test_catalunya_api.py
│   └── test_galicia_api.py
│
└── e2e/               # Tests end-to-end
    └── test_full_workflow.py
```

---

**Conclusión**: 
- ✅ **Estructura de tests**: Excelente, bien organizados
- ⚠️ **Ejecución**: Requiere servicios corriendo O ajustes en mocks
- 🎯 **Siguiente paso**: Decidir estrategia (Docker vs Mocks puros)
└── legacy/                        # Tests antiguos (referencia)
    ├── test_deteccion_duplicados.py
    ├── test_duplicados_bd.py
    └── ...
```

---

**Conclusión**: Los tests están bien estructurados, pero necesitan ajustes en imports y mocks para funcionar con la arquitectura de microservicios actual.
