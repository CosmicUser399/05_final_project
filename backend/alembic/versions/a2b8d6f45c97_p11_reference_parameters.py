"""p11_reference_parameters (M011 reference_parameters)

Revision ID: a2b8d6f45c97
Revises: f1a7c5e34b86
Create Date: 2026-10-04 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b8d6f45c97"
down_revision: Union[str, Sequence[str], None] = "f1a7c5e34b86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create reference_parameters table."""
    op.create_table(
        "reference_parameters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_class", sa.String(length=200), nullable=False),
        sa.Column(
            "equipment_class_code",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "failure_mode_code",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "failure_mode_name",
            sa.String(length=200),
            nullable=True,
        ),
        sa.Column("parameter_name", sa.String(length=200), nullable=False),
        sa.Column("parameter_kind", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column(
            "distribution_type",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column("distribution_params_json", sa.JSON(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_document", sa.String(length=300), nullable=False),
        sa.Column(
            "source_reference",
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["reference_sources.id"],
            name=op.f(
                "fk_reference_parameters_source_id_reference_sources"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_reference_parameters"),
        ),
    )
    op.create_index(
        op.f("ix_reference_parameters_source_id"),
        "reference_parameters",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reference_parameters_equipment_class"),
        "reference_parameters",
        ["equipment_class"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reference_parameters_equipment_class_code"),
        "reference_parameters",
        ["equipment_class_code"],
        unique=False,
    )


def downgrade() -> None:
    """Drop reference_parameters table."""
    op.drop_index(
        op.f("ix_reference_parameters_equipment_class_code"),
        table_name="reference_parameters",
    )
    op.drop_index(
        op.f("ix_reference_parameters_equipment_class"),
        table_name="reference_parameters",
    )
    op.drop_index(
        op.f("ix_reference_parameters_source_id"),
        table_name="reference_parameters",
    )
    op.drop_table("reference_parameters")
