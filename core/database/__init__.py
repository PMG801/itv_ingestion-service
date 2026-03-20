"""
Configuración de la base de datos usando SQLAlchemy 2.0 con soporte asíncrono.
Usa asyncpg como driver para PostgreSQL.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from core.config import settings


# Crear el motor asíncrono
async_engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI, 
    echo=settings.LOG_LEVEL == "DEBUG",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
)

# Crear el sessionmaker asíncrono
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# Base declarativa para los modelos ORM
class Base(DeclarativeBase):
    """
    Clase base para todos los modelos de SQLAlchemy.
    Hereda de DeclarativeBase (SQLAlchemy 2.0 style).
    """
    pass


# Dependencia para FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Alias de compatibilidad para código que usa el nombre antiguo
get_async_session = get_db


# Función para cerrar el engine al finalizar la aplicación
async def dispose_engine():
    await async_engine.dispose()
