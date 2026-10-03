"""p8_scenarios (M007 scenarios, scenario_versions, scenario_changes)

Revision ID: f1a7c5e34b86
Revises: e0f6b4d23a75
Create Date: 2026-10-04 05:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a7c5e34b86"
down_revision: Union[str, Sequence[str], None] = "e0f6b4d23a75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scenario tables and FK from simulation_runs."""
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
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
            ["version_id"],
            ["system_versions.id"],
            name=op.f("fk_scenarios_version_id_system_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenarios")),
    )
    op.create_index(
        op.f("ix_scenarios_version_id"),
        "scenarios",
        ["version_id"],
        unique=False,
    )

    op.create_table(
        "scenario_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("scenario_hash", sa.String(length=64), nullable=False),
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
            ["scenario_id"],
            ["scenarios.id"],
            name=op.f("fk_scenario_versions_scenario_id_scenarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_versions")),
        sa.UniqueConstraint(
            "scenario_id",
            "version_number",
            name="uq_scenario_versions_scenario_id_version_number",
        ),
    )
    op.create_index(
        op.f("ix_scenario_versions_scenario_id"),
        "scenario_versions",
        ["scenario_id"],
        unique=False,
    )

    op.create_table(
        "scenario_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_version_id", sa.Uuid(), nullable=False),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("target_lineage_id", sa.Uuid(), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
            ["scenario_version_id"],
            ["scenario_versions.id"],
            name=op.f(
                "fk_scenario_changes_scenario_version_id_scenario_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenario_changes")),
    )
    op.create_index(
        op.f("ix_scenario_changes_scenario_version_id"),
        "scenario_changes",
        ["scenario_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scenario_changes_target_lineage_id"),
        "scenario_changes",
        ["target_lineage_id"],
        unique=False,
    )

    with op.batch_alter_table("simulation_runs", schema=None) as batch_op:
        batch_op.create_foreign_key(
            op.f(
                "fk_simulation_runs_scenario_version_id_scenario_versions"
            ),
            "scenario_versions",
            ["scenario_version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    """Drop scenario FK and tables."""
    with op.batch_alter_table("simulation_runs", schema=None) as batch_op:
        batch_op.drop_constraint(
            op.f(
                "fk_simulation_runs_scenario_version_id_scenario_versions"
            ),
            type_="foreignkey",
        )

    op.drop_index(
        op.f("ix_scenario_changes_target_lineage_id"),
        table_name="scenario_changes",
    )
    op.drop_index(
        op.f("ix_scenario_changes_scenario_version_id"),
        table_name="scenario_changes",
    )
    op.drop_table("scenario_changes")
    op.drop_index(
        op.f("ix_scenario_versions_scenario_id"),
        table_name="scenario_versions",
    )
    op.drop_table("scenario_versions")
    op.drop_index(op.f("ix_scenarios_version_id"), table_name="scenarios")
    op.drop_table("scenarios")
