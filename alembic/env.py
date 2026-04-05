"""
Alembic Environment Configuration for Async SQLAlchemy.

Este módulo configura Alembic para trabajar con SQLAlchemy async + asyncpg.
Carga los modelos ORM y configura la metadata para autogeneración de migraciones.
"""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Añadir el directorio raíz al path para imports
root_path = Path(__file__).parent.parent
sys.path.insert(0, str(root_path))

# Importar configuración y Base
from core.config import settings
from core.database import Base

# Importar TODOS los modelos ORM para que estén en la metadata
# IMPORTANTE: Sin estos imports, Alembic no detectará las tablas
from domain.itv_stations.models import EstacionITV, IngestionLog  # noqa: F401

# Configuración de Alembic
config = context.config

# Override de la URL de BD desde settings (usa variable de entorno)
config.set_main_option("sqlalchemy.url", settings.SQLALCHEMY_DATABASE_URI)

# Configurar logging desde alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata target para autogeneración
# Contiene información de todas las tablas definidas en los modelos ORM
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Genera scripts SQL sin conectarse a la base de datos.
    Útil para generar SQL para revisión o aplicación manual.

    Uso: alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=config.get_main_option("version_table_schema"),
        compare_type=True,  # Detectar cambios en tipos de columnas
        compare_server_default=True,  # Detectar cambios en defaults
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    Ejecuta las migraciones con la conexión proporcionada.

    Args:
        connection: Conexión SQLAlchemy (síncrona, wrapeada desde async)
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=config.get_main_option("version_table_schema"),
        compare_type=True,  # Detectar cambios en tipos de columnas
        compare_server_default=True,  # Detectar cambios en defaults
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode con async engine.

    Crea un engine async, obtiene una conexión y ejecuta las migraciones
    de forma sincronizada dentro del contexto async.
    """
    # Crear engine async desde configuración
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No usar pool para migraciones
    )

    async with connectable.connect() as connection:
        # Ejecutar migraciones de forma síncrona dentro del contexto async
        await connection.run_sync(do_run_migrations)

    # Liberar recursos del engine
    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Wrapper que ejecuta las migraciones async usando asyncio.run().
    Este es el modo por defecto cuando ejecutas comandos Alembic.
    """
    asyncio.run(run_async_migrations())


# Determinar modo de ejecución
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
