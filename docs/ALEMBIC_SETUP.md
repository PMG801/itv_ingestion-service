# 🎯 Aplicar Migraciones de Alembic

Este documento explica los pasos para aplicar las migraciones de base de datos después de implementar Alembic.

## 📦 Paso 1: Instalar Alembic

```bash
# Si usas pip
pip install alembic==1.13.1 shapely

# Si usas PDM
pdm install
```

**Dependencias adicionales necesarias:**
- `shapely`: Para convertir coordenadas lat/lon a geometría PostGIS
- `geoalchemy2`: Ya está instalado (para soporte PostGIS)

## 🐘 Paso 2: Levantar PostgreSQL

```bash
# Levantar solo PostgreSQL
docker-compose up -d postgres

# Verificar que esté corriendo
docker ps | grep postgres
```

## 🗃️ Paso 3: Verificar extensiones PostgreSQL

Las extensiones se crean automáticamente con el nuevo [`init.sql`](../infra/postgres/init.sql):

```bash
make psql

# Dentro de psql, verificar:
SELECT * FROM pg_extension WHERE extname IN ('postgis', 'pg_trgm');

# Debería mostrar:
#  extname  | extversion 
# ----------+------------
#  postgis  | 3.x.x
#  pg_trgm  | 1.x

\q
```

## ▶️ Paso 4: Aplicar Migraciones

```bash
# Aplicar todas las migraciones pendientes
make migrate-up
```

**Salida esperada:**

```
⬆️  Aplicando migraciones...
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial, Crear tablas estaciones e ingestion_log
✅ Migraciones aplicadas
```

## ✅ Paso 5: Verificar las Tablas

```bash
make psql

# Ver tablas creadas en schema itv:
\dt itv.*

# Debería mostrar:
#  Schema |      Name       | Type  |   Owner   
# --------+-----------------+-------+-----------
#  itv    | alembic_version | table | itv_user
#  itv    | estaciones      | table | itv_user
#  itv    | ingestion_log   | table | itv_user

# Ver estructura de estaciones:
\d itv.estaciones

# Ver índices:
\di itv.*
```

## 🔍 Paso 6: Verificar Estado de Migraciones

```bash
make migrate-status
```

**Salida esperada:**

```
📊 Estado de migraciones:

▶️  Versión actual:
001_initial (head)

📜 Última migración aplicada:
001_initial -> Crear tablas estaciones e ingestion_log con indices optimizados
  Branch labels: 
  Depends on: 
  Path: /path/to/alembic/versions/001_initial.py
```

## 🧪 Paso 7: Probar Inserción Manual (Opcional)

Para verificar que todo funciona:

```bash
make psql
```

```sql
-- Insertar una estación de prueba
INSERT INTO itv.estaciones (
    fuente_origen, 
    id_en_fuente, 
    nombre, 
    latitud, 
    longitud,
    location,
    fecha_creacion,
    fecha_actualizacion
) VALUES (
    'catalunya',
    'TEST_001',
    'Estación de Prueba Barcelona',
    41.3851,
    2.1734,
    ST_SetSRID(ST_MakePoint(2.1734, 41.3851), 4326),
    NOW(),
    NOW()
);

-- Verificar inserción
SELECT id, fuente_origen, id_en_fuente, nombre, latitud, longitud 
FROM itv.estaciones 
WHERE id_en_fuente = 'TEST_001';

-- Limpiar
DELETE FROM itv.estaciones WHERE id_en_fuente = 'TEST_001';
```

## 🚀 Paso 8: Iniciar el Pipeline Completo

Ahora que la BD está lista, puedes levantar todos los servicios:

```bash
# Levantar todo (infraestructura + apps)
make up

# O por separado:
make up-infra   # RabbitMQ + PostgreSQL
make up-apps    # Gateway + Normalizer + Persister
```

## 🔧 Troubleshooting

### Error: "relation 'itv.alembic_version' already exists"

Si ya tenías una tabla `alembic_version` de pruebas anteriores:

```bash
make psql
DROP TABLE IF EXISTS itv.alembic_version CASCADE;
\q

make migrate-up
```

### Error: "extension 'pg_trgm' not available"

Si la extensión `pg_trgm` no está instalada en PostgreSQL:

```bash
make psql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
\q

make migrate-up
```

### Error: "ModuleNotFoundError: No module named 'shapely'"

```bash
pip install shapely
# O
pdm add shapely
```

### Ver logs detallados de Alembic

```bash
alembic upgrade head --verbose
```

### Verificar que el Persister puede conectar

```bash
# Levantar solo el Persister
docker-compose up persister

# Ver logs
docker-compose logs -f persister
```

Deberías ver:
```
persister_1  | INFO - Persister worker starting...
persister_1  | INFO - Conectando a RabbitMQ: amqp://...
persister_1  | INFO - ✓ Conectado a RabbitMQ
persister_1  | INFO - Esperando mensajes en cola 'normalized_data_queue'...
```

## 📊 Comandos Útiles Post-Migración

```bash
# Ver estado
make migrate-status

# Ver historial
make migrate-history

# Verificar salud de servicios
make check-health

# Ver logs del persister
make logs-persister

# Conectar a PostgreSQL
make psql

# Abrir RabbitMQ UI
make rabbitmq-ui
# http://localhost:15672 (admin/admin123)
```

## 📝 Próximos Pasos

1. **Probar ingesta completa:**
   ```bash
   # Enviar datos de prueba al Gateway
   curl -X POST http://localhost:8000/api/v1/ingest/catalunya \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
   
   # Verificar en la BD
   make psql
   SELECT * FROM itv.estaciones;
   ```

2. **Monitorear logs:**
   ```bash
   # Terminal 1: Gateway
   make logs-gateway
   
   # Terminal 2: Normalizer
   make logs-normalizer
   
   # Terminal 3: Persister
   make logs-persister
   ```

3. **Ver auditoría:**
   ```bash
   make psql
   SELECT * FROM itv.ingestion_log ORDER BY processed_at DESC LIMIT 10;
   ```

## 🎓 Para tu TFG

**Puntos a documentar:**

1. ✅ **Diseño de esquema flexible con JSONB**
   - Explica por qué elegiste `datos_extra` JSONB
   - Demuestra queries sobre el campo JSON

2. ✅ **Uso de PostGIS para datos geográficos**
   - Índice GIST para búsquedas espaciales eficientes
   - Queries de "estaciones cercanas"

3. ✅ **Migraciones versionadas con Alembic**
   - Comparar con enfoques raw SQL
   - Ventajas de autogeneración

4. ✅ **UPSERT pattern para deduplicación**
   - Explica el constraint único compuesto
   - Performance de ON CONFLICT DO UPDATE

5. ✅ **Auditoría completa con ingestion_log**
   - Trazabilidad de errores
   - Métricas de éxito/fallo

## 📚 Referencias

- [Guía completa de Alembic](./ALEMBIC_GUIDE.md)
- [Arquitectura del proyecto](./ARCHITECTURE_MAP.md)
- [Tech Stack](./TECH_STACK.md)
