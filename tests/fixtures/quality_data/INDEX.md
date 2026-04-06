# 🎯 Quality Control Data Files - Ficheros Preparados

## ✅ COMPLETADO - 3 Ficheros Fijos de Control de Calidad

Se han preparado **3 archivos fijos** con **diferentes formatos** para controlar la calidad de datos de cada fuente:

---

## 📦 Estructura Creada

```
tests/fixtures/quality_data/
├── 📄 README.md                      ← Documentación detallada
├── 📄 EXECUTION_GUIDE.md             ← Cómo ejecutar las pruebas
├── 📄 quality_test_catalunya.xml     ← Formato XML (Catalunya)
├── 📄 quality_test_valencia.json     ← Formato JSON (Valencia)  
├── 📄 quality_test_galicia.csv       ← Formato CSV (Galicia) [DIFERENTE]
├── 🐍 test_quality_data.py           ← Script automatizado de pruebas
└── 🐍 send_qa_messages.py            ← Script para enviar a RabbitMQ
```

---

## 📋 Ficheros de Datos

### 1️⃣ **quality_test_catalunya.xml** (Formato: XML)

**Contenido:** 12 registros de estaciones ITV de Catalunya

| Tipo | Cantidad | Ejemplo |
|------|----------|---------|
| ✅ Válidos | 3 | `CAT_BCN_001` - ITV Barcelona Nord |
| ⚠️ Edge Cases | 1 | Registro sin teléfono pero con email |
| ❌ Inválidos | 8 | Falta ID, coords inválidas, email malformado, etc |

**Estructura:**
```xml
<stations>
  <station>
    <id>CAT_BCN_001</id>
    <nom>ITV Barcelona Nord</nom>
    <latitud>41.3851</latitud>
    <longitud>2.1734</longitud>
    ...
  </station>
</stations>
```

---

### 2️⃣ **quality_test_valencia.json** (Formato: JSON)

**Contenido:** 17 registros de estaciones ITV de Valencia

| Tipo | Cantidad | Ejemplo |
|------|----------|---------|
| ✅ Válidos | 3 | `VAL_VLC_001` - ITV Valencia Centro |
| ⚠️ Edge Cases | 2 | Direcciones vacías, emails complejos |
| ❌ Inválidos | 12 | Falta código, coords fuera de rango, etc |

**Estructura:**
```json
{
  "estaciones": [
    {
      "codigo": "VAL_VLC_001",
      "nombre": "ITV Valencia Centro",
      "latitud": 39.4699,
      "longitud": -0.3763,
      ...
    }
  ]
}
```

---

### 3️⃣ **quality_test_galicia.csv** (Formato: CSV - DIFERENTE ✨)

**Contenido:** 13 registros de estaciones ITV de Galicia

| Tipo | Cantidad | Ejemplo |
|------|----------|---------|
| ✅ Válidos | 4 | `GAL_LU_001` - ITV Lugo Centro |
| ⚠️ Edge Cases | 1 | Registro sin teléfono |
| ❌ Inválidos | 8 | ID duplicado, coordenadas nulas, etc |

**Estructura:**
```csv
id,nome,enderezo,concello,provincia,cp,lat,lon,telefono,email
GAL_LU_001,ITV Lugo Centro,Rúa da Industria 123,Lugo,Lugo,27001,43.0097,-7.5567,982123456,info@lugo.gal
```

---

## 🧪 Errores Validados

Cada archivo contiene errores **intencionales** para validar que los normalizadores rechazan correctamente:

| Error | CAT | VAL | GAL | Descripción |
|-------|-----|-----|-----|-------------|
| **Missing ID** | ✓ | ✓ | ✓ | Campo requerido ausente |
| **Missing Name** | ✓ | ✓ | ✓ | Campo requerido ausente |
| **Invalid Latitude** | ✓ | ✓ | ✓ | Fuera de rango de España |
| **Invalid Longitude** | ✓ | ✓ | ✓ | Fuera de rango de España |
| **Invalid Email** | ✓ | ✓ | ✓ | Formato incorrecto |
| **Invalid Postal Code** | ✓ | ✓ | ✓ | No 5 dígitos |
| **Duplicate ID** | ✓ | ✓ | ✓ | ID repetido |
| **Null Coordinates** | - | ✓ | ✓ | Valores nulos |
| **Text in Numbers** | ✓ | ✓ | ✓ | Texto donde va número |

---

## 🚀 Cómo Usar

### Quick Start (5 minutos)
```bash
cd /home/pau/Desktop/TFG/project/itv-ingestion-service

# Ejecutar pruebas automatizadas
docker compose run --rm normalizer python tests/fixtures/quality_data/test_quality_data.py
```

### Opciones
```bash
# Opción 1: Ver logs en tiempo real
docker compose logs -f normalizer | grep quality

# Opción 2: Enviar a RabbitMQ (end-to-end)
docker compose run --rm gateway python tests/fixtures/quality_data/send_qa_messages.py

# Opción 3: Integrar en CI/CD
docker compose run --rm normalizer python -m pytest tests/fixtures/quality_data/
```

---

## 📊 Resultados Esperados

```
════════════════════════════════════════════════════════════
        QUALITY ASSURANCE TEST SUMMARY
════════════════════════════════════════════════════════════

Source          Valid    Rejected    Total    Pass Rate
─────────────────────────────────────────────────────────
CATALUNYA         3         9        12       25.0%  ✅
VALENCIA          3        14        17       17.6%  ✅
GALICIA           4         9        13       30.8%  ✅
─────────────────────────────────────────────────────────
TOTAL            10        32        42       23.8%  ✅
════════════════════════════════════════════════════════════

✨ Pass rate intencionalmente bajo - archivo de QA
```

---

## 📈 Cómo Evaluar Normalizers

Estos archivos te permiten:

✅ **Verificar parsing correcto** - Cada normalizer lee su formato  
✅ **Validar reglas de rechazo** - Inválidos se rechazan correctamente  
✅ **Comparar entre fuentes** - Comportamiento consistente  
✅ **Monitorear tendencias** - Ejecutar regularmente en CI/CD  
✅ **Entrenar desarrolladores** - Qué datos son válidos  

---

## 📚 Documentación

- **README.md** - Detalle técnico de cada archivo y campos
- **EXECUTION_GUIDE.md** - Pasos para ejecutar y interpretar resultados
- **test_quality_data.py** - Script Python automatizado
- **send_qa_messages.py** - Envía mensajes a RabbitMQ

---

## 🎓 Para Reproducir/Modificar

### Agregar más registros válidos
Edita cualquier archivo `.xml`, `.json` o `.csv` en esta carpeta y agrega nuevas estaciones

### Crear nuevos test cases
1. Duplica un archivo existente
2. Renómbralo (ej: `quality_test_extended.xml`)
3. Agrega nuevos casos de error
4. Ejecuta: `test_quality_data.py quality_test_extended.xml`

### Integrar en el pipeline
En tu CI/CD (GitHub Actions, GitLab CI, etc):
```yaml
test-quality:
  script:
    - docker compose run --rm normalizer python tests/fixtures/quality_data/test_quality_data.py
```

---

## ✨ Resumen Final

| Aspecto | Estado |
|--------|--------|
| **3 ficheros de datos** | ✅ Completado |
| **Formatos diferentes** | ✅ XML, JSON, CSV |
| **Casos válidos** | ✅ 10 registros |
| **Casos inválidos** | ✅ 32 registros |
| **Script de pruebas** | ✅ test_quality_data.py |
| **Script de RabbitMQ** | ✅ send_qa_messages.py |
| **Documentación** | ✅ README + EXECUTION_GUIDE |

---

**¿Listo para empezar?** → Ver [EXECUTION_GUIDE.md](EXECUTION_GUIDE.md)
