"""add persistent allocation recommendation history

Revision ID: d7f4c2a91e63
Revises: c41a7d9e2b60
Create Date: 2026-11-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7f4c2a91e63"
down_revision: Union[str, Sequence[str], None] = "c41a7d9e2b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "allocation_recommendations",
        sa.Column("recommendation_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.String(length=10), nullable=False),
        sa.Column("encounter_id", sa.Integer(), nullable=True),
        sa.Column("algorithm", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("recommended_bed_id", sa.String(length=10), nullable=True),
        sa.Column("proposed_action", sa.Integer(), nullable=True),
        sa.Column("final_action", sa.Integer(), nullable=True),
        sa.Column("proposed_bed_type", sa.String(length=30), nullable=True),
        sa.Column("final_bed_type", sa.String(length=30), nullable=True),
        sa.Column("safety_overridden", sa.Boolean(), nullable=True),
        sa.Column("safety_rule_triggered", sa.String(length=100), nullable=True),
        sa.Column("safety_original_action", sa.Integer(), nullable=True),
        sa.Column("safety_reason", sa.Text(), nullable=True),
        sa.Column("q_values", sa.JSON(), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.encounter_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.patient_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recommended_bed_id"], ["beds.bed_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("recommendation_id"),
    )
    op.create_index(
        "ix_allocation_recommendations_patient_created",
        "allocation_recommendations",
        ["patient_id", "created_at"],
    )
    op.create_index(
        "ix_allocation_recommendations_encounter_created",
        "allocation_recommendations",
        ["encounter_id", "created_at"],
    )
    op.create_index(
        "ix_allocation_recommendations_status_created",
        "allocation_recommendations",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_allocation_recommendations_status_created", table_name="allocation_recommendations")
    op.drop_index("ix_allocation_recommendations_encounter_created", table_name="allocation_recommendations")
    op.drop_index("ix_allocation_recommendations_patient_created", table_name="allocation_recommendations")
    op.drop_table("allocation_recommendations")
