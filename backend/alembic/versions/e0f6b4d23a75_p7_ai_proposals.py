"""p7_ai_proposals (M010 ai_runs, proposals, generation_jobs)

Revision ID: e0f6b4d23a75
Revises: d9e5a3c12f64
Create Date: 2026-10-04 04:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e0f6b4d23a75"
down_revision: Union[str, Sequence[str], None] = "d9e5a3c12f64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create AI / proposal / generation job tables."""
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_runs")),
    )

    op.create_table(
        "ai_generated_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_key", sa.String(length=128), nullable=False),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("value_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_ai_generated_values_ai_run_id_ai_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_generated_values")),
    )
    op.create_index(
        op.f("ix_ai_generated_values_ai_run_id"),
        "ai_generated_values",
        ["ai_run_id"],
        unique=False,
    )

    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("system_id", sa.Uuid(), nullable=True),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.String(length=128), nullable=True),
        sa.Column(
            "staging_schema_version",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("progress_pct", sa.Float(), nullable=False),
        sa.Column("progress_message", sa.String(length=500), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
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
            ["system_id"],
            ["systems.id"],
            name=op.f("fk_generation_jobs_system_id_systems"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["system_versions.id"],
            name=op.f("fk_generation_jobs_version_id_system_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_generation_jobs_ai_run_id_ai_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_jobs")),
    )
    op.create_index(
        op.f("ix_generation_jobs_status"),
        "generation_jobs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generation_jobs_system_id"),
        "generation_jobs",
        ["system_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generation_jobs_version_id"),
        "generation_jobs",
        ["version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generation_jobs_proposal_id"),
        "generation_jobs",
        ["proposal_id"],
        unique=False,
    )

    op.create_table(
        "proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("generation_job_id", sa.Uuid(), nullable=True),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("system_id", sa.Uuid(), nullable=True),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("provenance_json", sa.JSON(), nullable=False),
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
            ["generation_job_id"],
            ["generation_jobs.id"],
            name=op.f("fk_proposals_generation_job_id_generation_jobs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_proposals_ai_run_id_ai_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["system_id"],
            ["systems.id"],
            name=op.f("fk_proposals_system_id_systems"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["system_versions.id"],
            name=op.f("fk_proposals_version_id_system_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposals")),
    )
    op.create_index(
        op.f("ix_proposals_generation_job_id"),
        "proposals",
        ["generation_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_proposals_system_id"),
        "proposals",
        ["system_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_proposals_version_id"),
        "proposals",
        ["version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_proposals_status"),
        "proposals",
        ["status"],
        unique=False,
    )

    op.create_table(
        "proposal_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("item_type", sa.String(length=64), nullable=False),
        sa.Column("item_key", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("edited_payload_json", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["proposals.id"],
            name=op.f("fk_proposal_items_proposal_id_proposals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposal_items")),
    )
    op.create_index(
        op.f("ix_proposal_items_proposal_id"),
        "proposal_items",
        ["proposal_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop AI / proposal / generation job tables."""
    op.drop_index(
        op.f("ix_proposal_items_proposal_id"),
        table_name="proposal_items",
    )
    op.drop_table("proposal_items")
    op.drop_index(op.f("ix_proposals_status"), table_name="proposals")
    op.drop_index(op.f("ix_proposals_version_id"), table_name="proposals")
    op.drop_index(op.f("ix_proposals_system_id"), table_name="proposals")
    op.drop_index(
        op.f("ix_proposals_generation_job_id"),
        table_name="proposals",
    )
    op.drop_table("proposals")
    op.drop_index(
        op.f("ix_generation_jobs_proposal_id"),
        table_name="generation_jobs",
    )
    op.drop_index(
        op.f("ix_generation_jobs_version_id"),
        table_name="generation_jobs",
    )
    op.drop_index(
        op.f("ix_generation_jobs_system_id"),
        table_name="generation_jobs",
    )
    op.drop_index(
        op.f("ix_generation_jobs_status"),
        table_name="generation_jobs",
    )
    op.drop_table("generation_jobs")
    op.drop_index(
        op.f("ix_ai_generated_values_ai_run_id"),
        table_name="ai_generated_values",
    )
    op.drop_table("ai_generated_values")
    op.drop_table("ai_runs")
