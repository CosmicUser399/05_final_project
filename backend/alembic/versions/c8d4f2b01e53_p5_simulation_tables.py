"""p5_simulation_tables (M008 + M009)

Revision ID: c8d4f2b01e53
Revises: b7c3e1a90d42
Create Date: 2026-10-04 02:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d4f2b01e53"
down_revision: Union[str, Sequence[str], None] = "b7c3e1a90d42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create simulation configuration, runs, metrics and event tables."""
    op.create_table(
        "simulation_configurations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
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
            name=op.f(
                "fk_simulation_configurations_version_id_system_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_simulation_configurations"),
        ),
    )
    op.create_index(
        op.f("ix_simulation_configurations_version_id"),
        "simulation_configurations",
        ["version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulation_configurations_configuration_hash"),
        "simulation_configurations",
        ["configuration_hash"],
        unique=False,
    )

    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("reliability_model_id", sa.Uuid(), nullable=True),
        sa.Column("configuration_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("completed_runs", sa.Integer(), nullable=False),
        sa.Column("total_runs", sa.Integer(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("model_hash", sa.String(length=64), nullable=False),
        sa.Column("scenario_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "configuration_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("software_version", sa.String(length=64), nullable=False),
        sa.Column(
            "simulation_fingerprint",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aggregates_json", sa.JSON(), nullable=True),
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
            ["configuration_id"],
            ["simulation_configurations.id"],
            name=op.f(
                "fk_simulation_runs_configuration_id_"
                "simulation_configurations"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reliability_model_id"],
            ["reliability_models.id"],
            name=op.f(
                "fk_simulation_runs_reliability_model_id_reliability_models"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["system_versions.id"],
            name=op.f("fk_simulation_runs_version_id_system_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_runs")),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_simulation_runs_idempotency_key",
        ),
    )
    op.create_index(
        op.f("ix_simulation_runs_version_id"),
        "simulation_runs",
        ["version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulation_runs_configuration_id"),
        "simulation_runs",
        ["configuration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulation_runs_status"),
        "simulation_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulation_runs_simulation_fingerprint"),
        "simulation_runs",
        ["simulation_fingerprint"],
        unique=False,
    )

    op.create_table(
        "system_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("simulation_run_id", sa.Uuid(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["simulation_run_id"],
            ["simulation_runs.id"],
            name=op.f("fk_system_metrics_simulation_run_id_simulation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_metrics")),
        sa.UniqueConstraint(
            "simulation_run_id",
            name=op.f("uq_system_metrics_simulation_run_id"),
        ),
    )
    op.create_index(
        op.f("ix_system_metrics_simulation_run_id"),
        "system_metrics",
        ["simulation_run_id"],
        unique=False,
    )

    op.create_table(
        "equipment_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("simulation_run_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_id", sa.Uuid(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["simulation_run_id"],
            ["simulation_runs.id"],
            name=op.f(
                "fk_equipment_metrics_simulation_run_id_simulation_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_equipment_metrics")),
    )
    op.create_index(
        op.f("ix_equipment_metrics_simulation_run_id"),
        "equipment_metrics",
        ["simulation_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_equipment_metrics_equipment_id"),
        "equipment_metrics",
        ["equipment_id"],
        unique=False,
    )

    def _event_table(name: str, extra: list[sa.Column]) -> None:
        columns = [
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("simulation_run_id", sa.Uuid(), nullable=False),
            sa.Column("trial_run_id", sa.Integer(), nullable=False),
            sa.Column("timestamp_minutes", sa.Float(), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            *extra,
            sa.Column("details_json", sa.JSON(), nullable=False),
            sa.ForeignKeyConstraint(
                ["simulation_run_id"],
                ["simulation_runs.id"],
                name=op.f(f"fk_{name}_simulation_run_id_simulation_runs"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{name}")),
        ]
        op.create_table(name, *columns)
        op.create_index(
            op.f(f"ix_{name}_simulation_run_id"),
            name,
            ["simulation_run_id"],
            unique=False,
        )

    _event_table(
        "failure_events",
        [
            sa.Column("equipment_id", sa.Uuid(), nullable=True),
            sa.Column("failure_mode_id", sa.Uuid(), nullable=True),
        ],
    )
    op.create_index(
        op.f("ix_failure_events_equipment_id"),
        "failure_events",
        ["equipment_id"],
        unique=False,
    )
    op.create_index(
        "ix_failure_events_timestamp_minutes",
        "failure_events",
        ["timestamp_minutes"],
        unique=False,
    )

    _event_table(
        "maintenance_events",
        [
            sa.Column("equipment_id", sa.Uuid(), nullable=True),
            sa.Column("task_id", sa.Uuid(), nullable=True),
            sa.Column("failure_mode_id", sa.Uuid(), nullable=True),
        ],
    )
    op.create_index(
        op.f("ix_maintenance_events_equipment_id"),
        "maintenance_events",
        ["equipment_id"],
        unique=False,
    )
    op.create_index(
        "ix_maintenance_events_timestamp_minutes",
        "maintenance_events",
        ["timestamp_minutes"],
        unique=False,
    )

    _event_table(
        "diagnostic_events",
        [
            sa.Column("equipment_id", sa.Uuid(), nullable=True),
            sa.Column("task_id", sa.Uuid(), nullable=True),
            sa.Column("failure_mode_id", sa.Uuid(), nullable=True),
        ],
    )
    op.create_index(
        op.f("ix_diagnostic_events_equipment_id"),
        "diagnostic_events",
        ["equipment_id"],
        unique=False,
    )
    op.create_index(
        "ix_diagnostic_events_timestamp_minutes",
        "diagnostic_events",
        ["timestamp_minutes"],
        unique=False,
    )

    _event_table(
        "production_loss_events",
        [sa.Column("equipment_id", sa.Uuid(), nullable=True)],
    )
    op.create_index(
        op.f("ix_production_loss_events_equipment_id"),
        "production_loss_events",
        ["equipment_id"],
        unique=False,
    )
    op.create_index(
        "ix_production_loss_events_timestamp_minutes",
        "production_loss_events",
        ["timestamp_minutes"],
        unique=False,
    )

    _event_table(
        "resource_consumption",
        [
            sa.Column("resource_id", sa.Uuid(), nullable=True),
            sa.Column("equipment_id", sa.Uuid(), nullable=True),
        ],
    )
    op.create_index(
        op.f("ix_resource_consumption_resource_id"),
        "resource_consumption",
        ["resource_id"],
        unique=False,
    )
    op.create_index(
        "ix_resource_consumption_timestamp_minutes",
        "resource_consumption",
        ["timestamp_minutes"],
        unique=False,
    )

    _event_table(
        "spare_part_consumption",
        [
            sa.Column("spare_part_id", sa.Uuid(), nullable=True),
            sa.Column("equipment_id", sa.Uuid(), nullable=True),
        ],
    )
    op.create_index(
        op.f("ix_spare_part_consumption_spare_part_id"),
        "spare_part_consumption",
        ["spare_part_id"],
        unique=False,
    )
    op.create_index(
        "ix_spare_part_consumption_timestamp_minutes",
        "spare_part_consumption",
        ["timestamp_minutes"],
        unique=False,
    )


def downgrade() -> None:
    """Drop simulation tables."""
    for name in (
        "spare_part_consumption",
        "resource_consumption",
        "production_loss_events",
        "diagnostic_events",
        "maintenance_events",
        "failure_events",
        "equipment_metrics",
        "system_metrics",
        "simulation_runs",
        "simulation_configurations",
    ):
        op.drop_table(name)
