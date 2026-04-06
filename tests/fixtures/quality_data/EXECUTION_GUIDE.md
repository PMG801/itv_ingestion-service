# Guía de Ejecución - Quality Data Tests

## Resumen Rápido

Hemos creado **3 ficheros fijos de prueba** en esta carpeta para evaluar la calidad de datos de diferentes fuentes:

1. **quality_test_catalunya.xml** - Pruebas en formato XML (Catalunya)
2. **quality_test_valencia.json** - Pruebas en formato JSON (Valencia)
3. **quality_test_galicia.csv** - Pruebas en **formato diferente** CSV (Galicia)

---

## Cómo Usar

### ✅ Opción 1: Ejecutar el Script de Prueba (Recomendado)

#### Con Docker (Recommended)
```bash
# Desde la carpeta del proyecto
cd /home/pau/Desktop/TFG/project/itv-ingestion-service

# Ejecutar el script dentro del contenedor de normalización
docker compose run --rm normalizer python tests/fixtures/quality_data/test_quality_data.py
```

Este comando:
- Construye e inicia un contenedor con todas las dependencias
- Ejecuta el script de prueba automático
- Muestra un resumen de resultados
- Detiene el contenedor automáticamente

#### Localmente (si tienes Python 3.11+ configurado)
```bash
cd /home/pau/Desktop/TFG/project/itv-ingestion-service

# Installar dependencias del proyecto (una sola vez)
pip install -e .

# Ejecutar el test
python tests/fixtures/quality_data/test_quality_data.py
```

---

### 🧪 Opción 2: Pruebas Unitarias

Si prefieres mantener los tests dentro del framework de pruebas estándar del proyecto:

```bash
# Ejecutar solo tests de normalización
make test-normalizer

# Ejecutar todos los tests
make test-all

# Ejecutar un test específico
docker compose run --rm normalizer python -m pytest tests/ -v -k "quality"
```

---

### 📨 Opción 3: Pruebas con RabbitMQ (End-to-End)

Para enviar los archivos directamente a través de cola RabbitMQ:

```bash
# 1. Levantar todos los servicios
docker compose up -d

# 2. Esperar a que RabbitMQ esté listo (~10 segundos)
sleep 10

# 3. Enviar mensajes de prueba
docker compose run --rm gateway python -c "
from tests.fixtures.quality_data.send_qa_messages import send_all_quality_tests
send_all_quality_tests()
"

# 4. Verificar logs del normalizer
docker compose logs -f normalizer | grep "quality"

# 5. Ver resultados en PostgreSQL
docker compose exec db psql -U itv_user -d itv_db -c \
  'SELECT COUNT(*) FROM normalized_stations WHERE source_system IN (
    SELECT DISTINCT source_system FROM raw_ingestion_messages WHERE message_id LIKE \"qa-test%\"
  );'
```

---

## Estructura de Cada Archivo de Prueba

### quality_test_catalunya.xml
```
Registros: 12 total
├─ Válidos:    3 ✅
├─ Edge cases: 1 ⚠️
└─ Inválidos:  8 ❌
```

### quality_test_valencia.json
```
Registros: 17 total
├─ Válidos:    3 ✅
├─ Edge cases: 2 ⚠️
└─ Inválidos: 12 ❌
```

### quality_test_galicia.csv (FORMATO DIFERENTE)
```
Registros: 13 total
├─ Válidos:    4 ✅
├─ Edge cases: 1 ⚠️
└─ Inválidos:  8 ❌
```

---

## Qué Se Valida

✓ **Parsing correcto** - Cada normalizador puede leer su formato  
✓ **Validación de campos** - ID, nombre son requeridos  
✓ **Validación de coordenadas** - Dentro de límites de España  
✓ **Validación de email** - Formato correcto  
✓ **Validación de códigos postales** - 5 dígitos  
✓ **Detección de duplicados** - Mismo ID rechazado  
✓ **Manejo de errores** - Rechazo con motivo documentado  

---

## Resultados Esperados

#### Resumen de Ejecución
```
📊 OVERALL QUALITY SUMMARY
═══════════════════════════════════════
Source       Valid   Rejected  Pass Rate
───────────────────────────────────────
CATALUNYA      3        8        27.3%
VALENCIA       3       12        20.0%  
GALICIA        4        8        33.3%
───────────────────────────────────────
TOTAL         10       28        26.3%
═══════════════════════════════════════
```

La tasa de rechazo es **intencionalmente alta** porque los archivos están diseñados para QA. Los valididos deben procesarse sin problemas.

---

## Interpretación de Resultados

### ✅ Todo OK si:
- ✓ Válidos se procesan sin errores  
- ✓ Inválidos se rechazan con motivo ("missing_id", "invalid_email", etc.)
- ✓ Los 3 normalizadores manejan sus formatos correctamente  
- ✓ Sensibilidad a duplicados funciona

### ⚠️ Investigar si:
- ✗ Un record válido es rechazado  
- ✗ Un record inválido pasa sin ser rechazado  
- ✗ Hay excepciones/crashes  
- ✗ Los motivos de rechazo no son específicos

---

## Archivos de Soporte

- **test_quality_data.py** - Script automatizado para pruebas
- **README.md** - Documentación detallada de cada archivo
- **EXECUTION_GUIDE.md** - Guía que estás leyendo

---

## Próximos Pasos

1. ✅ **Ejecutar una vez** - Asegurar baseline de funcionamiento
2. 📊 **Integrar en CI/CD** - Agregar a pipeline de tests
3. 🔄 **Monitorear tendencias** - Comparar resultados en el tiempo
4. 📈 **Agregar casos** - Añadir nuevos test cases conforme descubras edge cases

---

**¿Necesitas ayuda?**  
Revisa los logs con: `docker compose logs normalizer`  
O examina los archivos de prueba directamente en esta carpeta.
