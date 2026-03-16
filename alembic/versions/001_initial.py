"""Crear tablas estaciones e ingestion_log con indices optimizados

Revision ID: 001_initial
Revises: 
Create Date: 2026-02-22 14:30:00.000000

Esta migración inicial crea:
1. Tabla estaciones: almacena datos normalizados de estaciones ITV
2. Tabla ingestion_log: auditoría del pipeline de ingesta
3. Índices optimizados para búsquedas (trigram, spatial, JSONB)
4. Función y trigger para auto-actualizar fecha_actualizacion
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Aplica los cambios: crea tablas, índices y triggers.
    """
    # ========================================================================
    # TABLA: estaciones
    # ========================================================================
    op.create_table(
        'estaciones',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fuente_origen', sa.String(length=50), nullable=False, comment='Sistema fuente de datos'),
        sa.Column('id_en_fuente', sa.String(length=100), nullable=False, comment='ID original en el sistema fuente'),
        sa.Column('nombre', sa.String(length=255), nullable=False, comment='Nombre de la estación ITV'),
        sa.Column('latitud', sa.Float(), nullable=True, comment='Latitud WGS84'),
        sa.Column('longitud', sa.Float(), nullable=True, comment='Longitud WGS84'),
        sa.Column('location', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True, comment='Punto geográfico PostGIS (SRID 4326 - WGS84)'),
        sa.Column('telefono', sa.String(length=20), nullable=True, comment='Número de teléfono'),
        sa.Column('email', sa.String(length=255), nullable=True, comment='Correo electrónico'),
        sa.Column('direccion', sa.Text(), nullable=True, comment='Dirección física completa'),
        sa.Column('codigo_postal', sa.String(length=10), nullable=True, comment='Código postal'),
        sa.Column('datos_extra', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Campos adicionales no mapeados en estructura JSON'),
        sa.Column('fecha_creacion', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Fecha de creación del registro'),
        sa.Column('fecha_actualizacion', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Fecha de última actualización (auto-gestionado por trigger)'),
        sa.CheckConstraint("fuente_origen IN ('catalunya', 'valencia', 'galicia')", name='ck_estaciones_fuente_valida'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fuente_origen', 'id_en_fuente', name='uq_estaciones_fuente_id'),
        schema='itv'
    )
    
    # Índices básicos (ya definidos en __table_args__)
    op.create_index('idx_estaciones_fuente', 'estaciones', ['fuente_origen'], unique=False, schema='itv')
    op.create_index('idx_estaciones_cp', 'estaciones', ['codigo_postal'], unique=False, schema='itv')
    
    # Índice GIN trigram para búsqueda fuzzy en nombre
    op.create_index(
        'idx_estaciones_nombre_trgm',
        'estaciones',
        ['nombre'],
        unique=False,
        schema='itv',
        postgresql_using='gin',
        postgresql_ops={'nombre': 'gin_trgm_ops'}
    )
    
    # NOTA: No creamos índice GIST para 'location' manualmente porque GeoAlchemy2
    # lo crea automáticamente al definir la columna Geometry con spatial_index=True (default)
    # Si quisiéramos uno personalizado, deberíamos usar raw SQL con IF NOT EXISTS
    
    # Índice GIN en JSONB para queries en datos_extra
    op.create_index(
        'idx_estaciones_datos_extra',
        'estaciones',
        ['datos_extra'],
        unique=False,
        schema='itv',
        postgresql_using='gin'
    )
    
    # ========================================================================
    # TABLA: ingestion_log
    # ========================================================================
    op.create_table(
        'ingestion_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=False, comment='ID único del mensaje RabbitMQ'),
        sa.Column('domain', sa.String(length=100), nullable=False, comment='Dominio de negocio'),
        sa.Column('source_system', sa.String(length=100), nullable=False, comment='Sistema fuente de los datos'),
        sa.Column('status', sa.String(length=50), nullable=False, comment='Estado: success, failed, processing'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Mensaje de error detallado'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()'), comment='Fecha y hora de procesamiento'),
        sa.CheckConstraint("status IN ('success', 'failed', 'processing')", name='ck_ingestion_log_status_valido'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id'),
        schema='itv'
    )
    
    # Índices para ingestion_log
    op.create_index('idx_ingestion_log_message_id', 'ingestion_log', ['message_id'], unique=False, schema='itv')
    op.create_index('idx_ingestion_log_status', 'ingestion_log', ['status'], unique=False, schema='itv')
    op.create_index('idx_ingestion_log_processed_at', 'ingestion_log', ['processed_at'], unique=False, schema='itv')
    
    # ========================================================================
    # TRIGGER: Auto-actualizar fecha_actualizacion en estaciones
    # ========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION itv.update_fecha_actualizacion()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.fecha_actualizacion = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER trigger_update_estaciones_fecha_actualizacion
        BEFORE UPDATE ON itv.estaciones
        FOR EACH ROW
        EXECUTE FUNCTION itv.update_fecha_actualizacion();
    """)


def downgrade() -> None:
    """
    Revierte los cambios: elimina triggers, índices y tablas.
    """
    # Eliminar trigger y función
    op.execute('DROP TRIGGER IF EXISTS trigger_update_estaciones_fecha_actualizacion ON itv.estaciones')
    op.execute('DROP FUNCTION IF EXISTS itv.update_fecha_actualizacion()')
    
    # Eliminar índices de ingestion_log
    op.drop_index('idx_ingestion_log_processed_at', table_name='ingestion_log', schema='itv')
    op.drop_index('idx_ingestion_log_status', table_name='ingestion_log', schema='itv')
    op.drop_index('idx_ingestion_log_message_id', table_name='ingestion_log', schema='itv')
    
    # Eliminar tabla ingestion_log
    op.drop_table('ingestion_log', schema='itv')
    
    # Eliminar índices de estaciones (creados manualmente)
    op.drop_index('idx_estaciones_datos_extra', table_name='estaciones', schema='itv')
    # No eliminamos idx_estaciones_location porque lo crea/elimina GeoAlchemy2 automáticamente
    op.drop_index('idx_estaciones_nombre_trgm', table_name='estaciones', schema='itv')
    op.drop_index('idx_estaciones_cp', table_name='estaciones', schema='itv')
    op.drop_index('idx_estaciones_fuente', table_name='estaciones', schema='itv')
    
    # Eliminar tabla estaciones (esto eliminará automáticamente el índice GIST de location)
    op.drop_table('estaciones', schema='itv')
