# Guía de Uso de Alembic

Esta guía explica cómo usar Alembic para gestionar las migraciones de base de datos en el proyecto.

## 📋 Prerequisitos

1. **Instalar Alembic** (ya está en pyproject.toml):
   ```bash
   pip install alembic==1.13.1
   # O si usas PDM:
   pdm install
   ```

2. **PostgreSQL corriendo** con las extensiones habilitadas:
   ```bash
   docker-compose up -d postgres
   ```

## 🚀 Comandos Rápidos

### Ver estado actual
```bash
make migrate-status
```

### Aplicar todas las migraciones
```bash
make migrate-up
```

### Crear nueva migración
```bash
make migrate-create MSG="Añadir campo telefono_secundario"
```

### Revertir última migración
```bash
make migrate-down
```

### Ver historial completo
```bash
make migrate-history
```

## 📖 Workflow Completo

### 1️⃣ Inicialización (Primera Vez)

Cuando clones el proyecto o inicies una BD nueva:

```bash
# 1. Levantar PostgreSQL
docker-compose up -d postgres

# 2. Aplicar migraciones iniciales
make migrate-up

# 3. Verificar que se crearon las tablas
make psql
# Dentro de psql:
\dt itv.*
```

Deberías ver:
- `itv.estaciones`
- `itv.ingestion_log`
- `itv.alembic_version`

### 2️⃣ Añadir un Campo Nuevo

Ejemplo: quieres añadir `horario_atencion` a la tabla `estaciones`.

**Paso 1: Modificar el modelo ORM**

Edita [`domain/itv_stations/models.py`](domain/itv_stations/models.py):

```python
class EstacionITV(Base):
    # ... campos existentes ...
    
    horario_atencion: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Horario de atención al público"
    )
```

**Paso 2: Generar migración automáticamente**

```bash
make migrate-create MSG="Añadir campo horario_atencion"
```

Esto crea un archivo en `alembic/versions/` tipo:
```
20260222_1430_abc123def456_añadir_campo_horario_atencion.py
```

**Paso 3: Revisar la migración generada**

Abre el archivo y verifica que Alembic detectó el cambio correctamente:

```python
def upgrade() -> None:
    op.add_column('estaciones', sa.Column('horario_atencion', sa.Text(), nullable=True), schema='itv')

def downgrade() -> None:
    op.drop_column('estaciones', 'horario_atencion', schema='itv')
```

**Paso 4: Aplicar la migración**

```bash
make migrate-up
```

**Paso 5: Verificar en la BD**

```bash
make psql
# Dentro de psql:
\d itv.estaciones
```

### 3️⃣ Modificar un Constraint o Índice

Ejemplo: quieres cambiar el constraint de `fuente_origen` para permitir 'murcia'.

**Paso 1: Modificar el modelo ORM**

En [`domain/itv_stations/models.py`](domain/itv_stations/models.py):

```python
CheckConstraint(
    "fuente_origen IN ('catalunya', 'valencia', 'galicia', 'murcia')",
    name="ck_estaciones_fuente_valida"
),
```

**Paso 2: Generar migración**

```bash
make migrate-create MSG="Permitir fuente murcia"
```

**Paso 3: Revisar y ajustar si es necesario**

Alembic podría no detectar cambios en constraints. En ese caso, edita manualmente:

```python
def upgrade() -> None:
    # Eliminar constraint anterior
    op.drop_constraint('ck_estaciones_fuente_valida', 'estaciones', schema='itv')
    
    # Crear nuevo constraint
    op.create_check_constraint(
        'ck_estaciones_fuente_valida',
        'estaciones',
        "fuente_origen IN ('catalunya', 'valencia', 'galicia', 'murcia')",
        schema='itv'
    )

def downgrade() -> None:
    op.drop_constraint('ck_estaciones_fuente_valida', 'estaciones', schema='itv')
    op.create_check_constraint(
        'ck_estaciones_fuente_valida',
        'estaciones',
        "fuente_origen IN ('catalunya', 'valencia', 'galicia')",
        schema='itv'
    )
```

**Paso 4: Aplicar**

```bash
make migrate-up
```

### 4️⃣ Añadir Datos Maestros (Seed)

Ejemplo: poblar provincias de España.

**Crear migración manual:**

```bash
alembic revision -m "Seed provincias españolas"
```

Editar el archivo generado:

```python
def upgrade() -> None:
    # Crear tabla temporal de provincias (si no existe)
    op.execute("""
        CREATE TABLE IF NOT EXISTS itv.provincias (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) UNIQUE NOT NULL
        );
    """)
    
    # Insertar provincias
    op.execute("""
        INSERT INTO itv.provincias (nombre) VALUES
            ('Barcelona'), ('Girona'), ('Lleida'), ('Tarragona'),
            ('Valencia'), ('Alicante'), ('Castellón'),
            ('A Coruña'), ('Lugo'), ('Ourense'), ('Pontevedra')
        ON CONFLICT (nombre) DO NOTHING;
    """)

def downgrade() -> None:
    op.execute("DELETE FROM itv.provincias WHERE nombre IN ('Barcelona', 'Girona', ...)")
```

Aplicar:

```bash
make migrate-up
```

## 🔍 Debugging

### Ver qué migración está aplicada

```bash
make migrate-status
```

Salida:
```
📊 Estado de migraciones:

▶️  Versión actual:
001_initial (head)

📜 Última migración aplicada:
001_initial -> Crear tablas estaciones e ingestion_log
```

### Ver SQL generado sin ejecutar

```bash
make migrate-sql > preview.sql
cat preview.sql
```

### Problema: Migración falló a medias

Si una migración falla parcialmente:

1. **Revisar estado:**
   ```bash
   make psql
   SELECT * FROM itv.alembic_version;
   ```

2. **Opciones:**
   - Si la tabla `alembic_version` apunta a la migración fallida pero no se aplicó:
     ```bash
     # Marcar como no aplicada manualmente
     make psql
     DELETE FROM itv.alembic_version WHERE version_num = 'abc123';
     ```
   
   - Si se aplicó parcialmente, revertir manualmente el SQL:
     ```bash
     make psql
     -- Ejecutar comandos DROP/DELETE según lo que se creó
     ```

## ⚠️ Mejores Prácticas

### ✅ DO

- **Revisar siempre** el archivo de migración antes de aplicar
- **Probar migraciones** en entorno de desarrollo primero
- **Hacer backup** de BD en producción antes de migrar
- **Commitear migraciones** junto con cambios de código
- **Nombres descriptivos**: `make migrate-create MSG="Añadir índice performance en estaciones"`

### ❌ DON'T

- No edites migraciones ya aplicadas en otros entornos
- No hagas cambios manuales en BD que Alembic no conozca
- No elimines archivos de `alembic/versions/`
- No modifiques el `revision` o `down_revision` de migraciones

## 🆘 Comandos de Emergencia

### Resetear completamente Alembic (PELIGRO)

Solo en desarrollo, si algo se rompió:

```bash
make migrate-reset
# Confirmar con "SI"

# Volver a aplicar desde cero
make migrate-up
```

### Ver diferencias entre modelos y BD

```bash
alembic check
```

Si hay diferencias, genera una migración:
```bash
make migrate-create MSG="Sincronizar cambios pendientes"
```

## 📚 Referencias

- Documentación oficial: https://alembic.sqlalchemy.org/
- Tutorial async: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
