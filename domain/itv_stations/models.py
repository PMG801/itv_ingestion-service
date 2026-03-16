"""
SQLAlchemy ORM models for ITV stations domain.

Este módulo define los modelos de base de datos usando SQLAlchemy 2.0.
Todos los modelos heredan de Base (DeclarativeBase) y residen en el schema 'itv'.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String,
    Text,
    Float,
    Integer,
    DateTime,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry

from core.database import Base


class EstacionITV(Base):
    """
    Modelo ORM para estaciones ITV.
    
    Representa una estación de inspección técnica de vehículos con datos normalizados
    de múltiples fuentes (Catalunya, Valencia, Galicia). Incluye campos estructurados
    para consultas eficientes y un campo JSONB flexible para datos adicionales.
    
    Attributes:
        id: Clave primaria autoincremental
        fuente_origen: Sistema fuente ('catalunya', 'valencia', 'galicia')
        id_en_fuente: ID original en el sistema fuente (para deduplicación)
        nombre: Nombre normalizado de la estación
        latitud: Coordenada latitud (WGS84)
        longitud: Coordenada longitud (WGS84)
        location: Punto geométrico PostGIS (SRID 4326)
        telefono: Número de contacto
        email: Email de contacto
        direccion: Dirección completa normalizada
        codigo_postal: Código postal español (5 dígitos)
        datos_extra: Campos adicionales no mapeados en formato JSONB
        fecha_creacion: Timestamp de primera inserción (UTC)
        fecha_actualizacion: Timestamp de última modificación (UTC, auto-actualizado)
    """
    
    __tablename__ = "estaciones"
    __table_args__ = (
        # Constraint único: evitar duplicados por fuente + ID original
        UniqueConstraint(
            "fuente_origen",
            "id_en_fuente",
            name="uq_estaciones_fuente_id"
        ),
        # Validar que fuente_origen sea una de las permitidas
        CheckConstraint(
            "fuente_origen IN ('catalunya', 'valencia', 'galicia')",
            name="ck_estaciones_fuente_valida"
        ),
        # NOTA: Los índices se crean en la migración de Alembic (001_initial.py)
        # para tener control completo sobre tipos especiales (GIN, GIST)
        # Schema PostgreSQL
        {"schema": "itv"},
    )
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Campos de identificación y origen
    fuente_origen: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Sistema fuente de datos"
    )
    id_en_fuente: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="ID original en el sistema fuente"
    )
    
    # Datos normalizados obligatorios
    nombre: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Nombre de la estación ITV"
    )
    
    # Coordenadas geográficas (opcionales)
    latitud: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Latitud WGS84"
    )
    longitud: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Longitud WGS84"
    )
    
    # Geometría PostGIS (generada desde latitud/longitud)
    location: Mapped[Optional[Geometry]] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=True,
        comment="Punto geográfico PostGIS (SRID 4326 - WGS84)"
    )
    
    # Datos de contacto (opcionales)
    telefono: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Número de teléfono"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Correo electrónico"
    )
    
    # Dirección (opcional)
    direccion: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Dirección física completa"
    )
    codigo_postal: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Código postal"
    )
    
    # Datos adicionales flexibles (JSONB)
    datos_extra: Mapped[Optional[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Campos adicionales no mapeados en estructura JSON"
    )
    
    # Timestamps de auditoría
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Fecha de creación del registro"
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="Fecha de última actualización (auto-gestionado por trigger)"
    )
    
    def __repr__(self) -> str:
        return (
            f"<EstacionITV(id={self.id}, "
            f"fuente={self.fuente_origen}, "
            f"id_fuente={self.id_en_fuente}, "
            f"nombre='{self.nombre}')>"
        )


class IngestionLog(Base):
    """
    Modelo ORM para log de auditoría del pipeline de ingesta.
    
    Registra cada mensaje procesado por el sistema con su estado final,
    permitiendo debugging y trazabilidad de errores.
    
    Attributes:
        id: Clave primaria autoincremental
        message_id: ID único del mensaje RabbitMQ
        domain: Dominio de negocio ('itv_stations', etc.)
        source_system: Sistema fuente del dato
        status: Estado final del procesamiento
        error_message: Mensaje de error si falló
        processed_at: Timestamp del procesamiento (UTC)
    """
    
    __tablename__ = "ingestion_log"
    __table_args__ = (
        # NOTA: Los índices se crean en la migración de Alembic (001_initial.py)
        # Validar estados permitidos
        CheckConstraint(
            "status IN ('success', 'failed', 'processing')",
            name="ck_ingestion_log_status_valido"
        ),
        # Schema PostgreSQL
        {"schema": "itv"},
    )
    
    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Identificación del mensaje
    message_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="ID único del mensaje RabbitMQ"
    )
    
    # Clasificación
    domain: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Dominio de negocio"
    )
    source_system: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Sistema fuente de los datos"
    )
    
    # Estado del procesamiento
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Estado: success, failed, processing"
    )
    
    # Detalles de error (si aplica)
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Mensaje de error detallado"
    )
    
    # Timestamp
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="Fecha y hora de procesamiento"
    )
    
    def __repr__(self) -> str:
        return (
            f"<IngestionLog(id={self.id}, "
            f"message_id='{self.message_id}', "
            f"status='{self.status}')>"
        )

