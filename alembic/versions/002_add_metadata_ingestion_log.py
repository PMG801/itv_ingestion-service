"""Agregar columna metadata JSONB a ingestion_log para trazabilidad de tiempos

Revision ID: 002_add_metadata
Revises: 001_initial
Create Date: 2026-03-20 12:00:00.000000

Esta migración extiende la tabla ingestion_log con:
1. Columna metadata JSONB para almacenar:
   - Timing de cada etapa (gateway/normalizer/persister)
   - Tipo de inyección (api/file/synthetic)
   - Resumen de rechazos (counts y razones)
   - Snapshots de profundidad de colas
2. Índice GIN en metadata para queries eficientes
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_metadata'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Agregar columna metadata a ingestion_log.
    """
    # Agregar columna metadata JSONB con default vacío
    op.add_column(
        'ingestion_log',
        sa.Column(
            'metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default='{}',
            comment='Metadatos de timing, inyección y trazabilidad (JSONB)'
        ),
        schema='itv'
    )

    # Crear índice GIN en metadata para queries eficientes en JSONB
    op.create_index(
        'idx_ingestion_log_metadata',
        'ingestion_log',
        ['metadata'],
        unique=False,
        schema='itv',
        postgresql_using='gin'
    )


def downgrade() -> None:
    """
    Revertir los cambios: eliminar índice y columna metadata.
    """
    # Eliminar índice
    op.drop_index('idx_ingestion_log_metadata', table_name='ingestion_log', schema='itv')

    # Eliminar columna metadata
    op.drop_column('ingestion_log', 'metadata', schema='itv')
