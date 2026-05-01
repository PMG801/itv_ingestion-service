"""Crear tabla llm_mapping_rules para almacenar reglas aprendidas por LLM

Revision ID: 003_add_llm_mapping_rules
Revises: 002_add_metadata
Create Date: 2026-04-26 10:00:00.000000

Esta migración crea la tabla llm_mapping_rules para almacenar reglas de mapeo
aprendidas por el LLM durante normalización. Cada regla se identifica por
(source_system, province_type) y contiene el mapeo de campos descubierto.

Características:
1. Constraint único: solo una regla activa por (source_system, province_type)
2. Versionado: se mantiene histórico de reglas inactivas
3. Trazabilidad: metadatos del modelo LLM y prompt version
4. Índice: búsqueda rápida por (source_system, province_type, is_active)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003_add_llm_mapping_rules"
down_revision: Union[str, None] = "002_add_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Crear tabla llm_mapping_rules en schema itv.
    """
    op.create_table(
        "llm_mapping_rules",
        sa.Column(
            "id", sa.Integer(), nullable=False, comment="Clave primaria autoincremental"
        ),
        sa.Column(
            "source_system",
            sa.String(50),
            nullable=False,
            comment="Sistema fuente (catalunya, valencia, galicia)",
        ),
        sa.Column(
            "province_type",
            sa.String(100),
            nullable=False,
            comment="Tipo de provincia que genera este patrón",
        ),
        sa.Column(
            "field_mapping",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Mapeo de campos descubierto: {source_field: target_field}",
        ),
        sa.Column(
            "llm_model",
            sa.String(255),
            nullable=False,
            comment="Nombre del modelo LLM usado (e.g., 'gpt-4', 'llama3-8b')",
        ),
        sa.Column(
            "llm_prompt_version",
            sa.String(50),
            nullable=False,
            server_default="1.0",
            comment="Versión del prompt usado",
        ),
        sa.Column(
            "confidence_score",
            sa.Float(),
            nullable=False,
            comment="Confianza del LLM (0.0-1.0)",
        ),
        sa.Column(
            "sample_schema_signature",
            sa.String(255),
            nullable=True,
            comment="Firma SHA256 del esquema del ejemplo usado",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="Si esta regla es la activa actualmente",
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timestamp de generación de la regla por LLM",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Timestamp de última actualización",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Timestamp de creación en base de datos",
        ),
        sa.CheckConstraint(
            "source_system IN ('catalunya', 'valencia', 'galicia')",
            name="ck_llm_rules_source_valida",
        ),
        sa.CheckConstraint(
            "is_active IN (true, false)",
            name="ck_llm_rules_is_active_bool",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "province_type",
            "is_active",
            name="uq_llm_rules_active_per_source_type",
            postgresql_where=sa.text("is_active = true"),
        ),
        schema="itv",
    )

    # Crear índice compuesto para búsqueda rápida
    op.create_index(
        "idx_llm_rules_source_type_active",
        "llm_mapping_rules",
        ["source_system", "province_type", "is_active"],
        schema="itv",
    )

    # Crear índice en generated_at para análisis temporal
    op.create_index(
        "idx_llm_rules_generated_at",
        "llm_mapping_rules",
        ["generated_at"],
        schema="itv",
    )


def downgrade() -> None:
    """
    Eliminar tabla llm_mapping_rules.
    """
    # Eliminar índices
    op.drop_index(
        "idx_llm_rules_generated_at",
        table_name="llm_mapping_rules",
        schema="itv",
    )
    op.drop_index(
        "idx_llm_rules_source_type_active",
        table_name="llm_mapping_rules",
        schema="itv",
    )

    # Eliminar tabla
    op.drop_table("llm_mapping_rules", schema="itv")
