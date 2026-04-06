# Quality Data Test Files - Ficheros de Prueba de Calidad

Esta carpeta contiene **3 ficheros de prueba fijos** con diferentes formatos para validar la **calidad de datos** y el comportamiento de los **normalizadores** (`CatalunyaTransformer`, `ValenciaTransformer`, `GaliciaTransformer`).

## Estructura de archivos de prueba

### 1. **quality_test_catalunya.xml** - Formato XML
- **Fuente:** Catalunya
- **Formato:** XML (con estructura `<stations><station>...</station></stations>`)
- **Propósito:** Validar normalización XML y reglas de calidad
- **Casos incluidos:** 12 registros (3 válidos, 1 edge case, 8 inválidos)

#### Campos XML
```xml
<id>              <!-- Station ID (required) -->
<nom>             <!-- Name in Catalan (required) -->
<adreca>          <!-- Address -->
<ciutat>          <!-- City -->
<provincia>       <!-- Province -->
<codi_postal>     <!-- Postal Code (5 digits) -->
<latitud>         <!-- Latitude (36-43.5 for Spain) -->
<longitud>        <!-- Longitude (-9 to 3 for Spain) -->
<telefon>         <!-- Phone number -->
<email>           <!-- Email address -->
```

---

### 2. **quality_test_valencia.json** - Formato JSON
- **Fuente:** Valencia  
- **Formato:** JSON con array `estaciones` dentro de un objeto raíz
- **Propósito:** Validar normalización JSON y reglas de calidad
- **Casos incluidos:** 17 registros (3 válidos, 2 edge cases, 12 inválidos)

#### Estructura JSON
```json
{
  "estaciones": [
    {
      "codigo": "VAL_VLC_001",           // Station ID (required)
      "nombre": "ITV Valencia Centro",   // Name (required)
      "direccion": "Calle de la...",    // Address
      "poblacion": "Valencia",           // City
      "provincia": "Valencia",           // Province
      "codigo_postal": "46001",         // Postal code
      "latitud": 39.4699,               // Latitude (float)
      "longitud": -0.3763,              // Longitude (float)
      "telefono": "963456789",          // Phone
      "correo": "info@email.es"         // Email
    }
  ]
}
```

---

### 3. **quality_test_galicia.csv** - Formato CSV (FORMATO DIFERENTE)
- **Fuente:** Galicia
- **Formato:** CSV con encabezados: `id,nome,enderezo,concello,provincia,cp,lat,lon,telefono,email`
- **Propósito:** Validar normalización CSV (formato diferente) y reglas de calidad
- **Casos incluidos:** 13 registros (4 válidos, 1 edge case, 8 inválidos)

#### Estructura CSV
```
id              | Station ID (required)
nome            | Name in Galician (required)
enderezo        | Address
concello        | City/Municipality
provincia       | Province
cp              | Postal code (5 digits)
lat             | Latitude (float)
lon             | Longitude (float)
telefono        | Phone number
email           | Email address
```

---

## Casos de Prueba Incluidos

### ✅ VALID RECORDS (Registros Válidos)
Los archivos incluyen **3-4 registros completamente válidos** con:
- Todos los campos requeridos presentes
- Formato correcto (emails válidos, códigos postales 5 dígitos)
- Coordenadas dentro de límites geográficos de España
- Datos realistas de estaciones ITV

**Resultado esperado:** ✅ Normalizados sin rechazos

---

### ⚠️ EDGE CASES (Casos Límite)
Registros técnicamente válidos pero con **datos potencialmente problemáticos**:
- Campos opcionales faltantes (teléfono vacío, dirección vacía)
- Emails complejos con caracteres especiales (`+`, `.`)
- Datos mínimos pero completos

**Resultado esperado:** ✅ Normalizados (pero verificar si requieren manejo especial)

---

### ❌ INVALID RECORDS (Registros Inválidos)
Incluyen **8-12 errores diferentes** por archivo para validar rechazo:

| Tipo de Error | Descripción | Resultado Esperado |
|---|---|---|
| **Missing Required Field** | ID o nombre faltante | ❌ Rejected |
| **Invalid Coordinates** | Latitud/longitud fuera de rango de España | ❌ Rejected |
| **Invalid Email** | Formato email incorrecto | ❌ Rejected |
| **Invalid Postal Code** | No 5 dígitos (too short/long/letters) | ❌ Rejected |
| **Duplicate ID** | Mismo ID en múltiples registros | ❌ Rejected (second) |
| **Malformed Number** | Texto en lugar de número (coords) | ❌ Rejected |
| **Null Values** | Coordenadas null en JSON | ❌ Rejected |
| **Empty Required Fields** | Campos requeridos vacíos | ❌ Rejected |

---

## Cómo Usar para QA

### 1️⃣ Test Individual Files Directly
```bash
# Test Catalunya XML
python -c "
from domain.itv_stations.transformers.factory import TransformerFactory
import xml.etree.ElementTree as ET

transformer = TransformerFactory.create('catalunya')
with open('tests/fixtures/quality_data/quality_test_catalunya.xml') as f:
    result = transformer.transform(f.read())
    
print(f'Valid records: {len(result)}')
print(f'Rejected items: {transformer.rejected_items}')
"

# Test Valencia JSON
python -c "
from domain.itv_stations.transformers.factory import TransformerFactory
import json

transformer = TransformerFactory.create('valencia')
with open('tests/fixtures/quality_data/quality_test_valencia.json') as f:
    data = json.load(f)
    result = transformer.transform(data)
    
print(f'Valid records: {len(result)}')
print(f'Rejected items: {len(transformer.rejected_items)}')
"

# Test Galicia CSV
python -c "
from domain.itv_stations.transformers.factory import TransformerFactory

transformer = TransformerFactory.create('galicia')
with open('tests/fixtures/quality_data/quality_test_galicia.csv') as f:
    result = transformer.transform(f.read())
    
print(f'Valid records: {len(result)}')
print(f'Rejected items: {len(transformer.rejected_items)}')
"
```

### 2️⃣ Create RabbitMQ Test Messages
Envía cada archivo como mensaje a través del Gateway:

```python
import json
import base64
from datetime import datetime

def create_message(file_path, source_system, format_type):
    with open(file_path, 'rb') as f:
        raw_content = f.read()
    
    message = {
        "header": {
            "message_id": f"qa-test-{source_system}-{datetime.now().timestamp()}",
            "timestamp": datetime.now().isoformat(),
            "domain": "itv_stations",
            "source_system": source_system,
            "content_type": f"application/{format_type}"
        },
        "payload": {
            "raw_content": base64.b64encode(raw_content).decode()
        }
    }
    return json.dumps(message)

# Create test messages
cat_msg = create_message('quality_test_catalunya.xml', 'catalunya', 'xml')
val_msg = create_message('quality_test_valencia.json', 'valencia', 'json')
gal_msg = create_message('quality_test_galicia.csv', 'galicia', 'csv')
```

### 3️⃣ Check Quality Metrics
Después de procesar los mensajes:
- **Valid Rate:** `#normalized / (#normalized + #rejected)`
- **Rejection Breakdown:** Contar rechazos por tipo de error
- **Format Compatibility:** Verificar que cada formato procesa esperando sus estructuras

---

## Validación Cruzada: Diferentes Normalizadores

Estos archivos permiten **comparar comportamiento entre normalizadores**:

| Aspecto | Catalunya (XML) | Valencia (JSON) | Galicia (CSV) |
|---|---|---|---|
| **Format** | XML | JSON | CSV |
| **Encoding** | Text | Text | CSV dialect |
| **Parser** | ElementTree | json module | csv module |
| **Field Names** | Catalan | Spanish | Galician/Spanish |
| **Coord Format** | Text (`,` decimal) | Numbers | Text (`.` decimal) |
| **Validation** | Source-specific | Source-specific | Source-specific |

---

## Expected Results Summary

```
📊 EXPECTED QUALITY BASELINE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Catalunya XML:   3 valid / ~8 rejected ≈ 27% pass rate
Valencia JSON:   5 valid / ~12 rejected ≈ 29% pass rate  
Galicia CSV:     5 valid / ~8 rejected ≈ 38% pass rate
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Average pass rate: ~31% ✓
(Low percentage expected - designed for QA testing)
```

Estos archivos pueden reevaluarse para:**- Detectar cambios en calidad de datos de fuentes**
- **Validar cambios en reglas de normalización**
- **Comparar comportamiento entre versiones de normalizadores**
- **Entrenar a desarrolladores sobre qué datos son válidos**
