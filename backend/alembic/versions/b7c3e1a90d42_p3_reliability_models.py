"""p3_reliability_models

Revision ID: b7c3e1a90d42
Revises: 5a4e8291af21
Create Date: 2026-10-04 01:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c3e1a90d42"
down_revision: Union[str, Sequence[str], None] = "5a4e8291af21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create reliability_models table."""
    op.create_table(
        "reliability_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("model_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column(
            "validation_status",
            sa.String(length=32),
            nullable=False,
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
            name=op.f(
                "fk_reliability_models_version_id_system_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_reliability_models"),
        ),
    )
    op.create_index(
        op.f("ix_reliability_models_version_id"),
        "reliability_models",
        ["version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reliability_models_model_hash"),
        "reliability_models",
        ["model_hash"],
        unique=False,
    )


def downgrade() -> None:
    """Drop reliability_models table."""
    op.drop_index(
        op.f("ix_reliability_models_model_hash"),
        table_name="reliability_models",
    )
    op.drop_index(
        op.f("ix_reliability_models_version_id"),
        table_name="reliability_models",
    )
    op.drop_table("reliability_models")
