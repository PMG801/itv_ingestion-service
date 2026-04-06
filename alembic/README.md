# Alembic Migrations

Este directorio contiene todas las migraciones de base de datos del proyecto,
gestionadas por Alembic.

## Estructura

- `versions/`: Contiene los archivos de migración versionados
- `env.py`: Configuración del entorno Alembic (async + asyncpg)
- `script.py.mako`: Template para generar nuevos archivos de migración

## Comandos principales

Ver el Makefile en la raíz del proyecto para helpers:

```bash
# Crear nueva migración (autogenera desde modelos ORM)
make migrate-create MSG="descripcion del cambio"

# Aplicar todas las migraciones pendientes
make migrate-up

# Revertir última migración
make migrate-down

# Ver estado actual
make migrate-status

# Ver historial completo
make migrate-history
```

## Workflow típico

1. Modificar modelos ORM en `domain/itv_stations/models.py`
2. Generar migración: `make migrate-create MSG="Añadir campo X"`
3. Revisar el archivo generado en `alembic/versions/`
4. Aplicar migración: `make migrate-up`

## Notas

- Las migraciones se ejecutan en modo async con asyncpg
- La tabla `alembic_version` vive en el schema `itv`
- Todas las tablas se crean en el schema `itv`
