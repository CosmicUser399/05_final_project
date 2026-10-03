"""p6_petri_models (M006 petri_models)

Revision ID: d9e5a3c12f64
Revises: c8d4f2b01e53
Create Date: 2026-10-04 03:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e5a3c12f64"
down_revision: Union[str, Sequence[str], None] = "c8d4f2b01e53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create petri_models table."""
    op.create_table(
        "petri_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("reliability_model_id", sa.Uuid(), nullable=True),
        sa.Column(
            "reliability_model_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("definition_json", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column(
            "validation_status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "petri_pilot_version",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["system_versions.id"],
            name=op.f("fk_petri_models_version_id_system_versions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reliability_model_id"],
            ["reliability_models.id"],
            name=op.f(
                "fk_petri_models_reliability_model_id_reliability_models"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_petri_models")),
    )
    op.create_index(
        op.f("ix_petri_models_version_id"),
        "petri_models",
        ["version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_petri_models_reliability_model_id"),
        "petri_models",
        ["reliability_model_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_petri_models_reliability_model_hash"),
        "petri_models",
        ["reliability_model_hash"],
        unique=False,
    )


def downgrade() -> None:
    """Drop petri_models table."""
    op.drop_index(
        op.f("ix_petri_models_reliability_model_hash"),
        table_name="petri_models",
    )
    op.drop_index(
        op.f("ix_petri_models_reliability_model_id"),
        table_name="petri_models",
    )
    op.drop_index(
        op.f("ix_petri_models_version_id"),
        table_name="petri_models",
    )
    op.drop_table("petri_models")
