"""add encounters and resource assignment history

Revision ID: c41a7d9e2b60
Revises: e3d8f1c49b20
Create Date: 2026-11-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c41a7d9e2b60"
down_revision: Union[str, Sequence[str], None] = "e3d8f1c49b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Legacy OCCUPIED beds and IN_USE equipment are deliberately not backfilled:
    # ownership is unknown and requires explicit reconciliation before lifecycle
    # operations manage those resources.
    op.create_table(
        "encounters",
        sa.Column("encounter_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.String(length=10), nullable=False),
        sa.Column("acuity", sa.Integer(), nullable=False),
        sa.Column("specialty", sa.String(length=50), nullable=False),
        sa.Column("predicted_los", sa.Float(), nullable=False),
        sa.Column("isolation_required", sa.Boolean(), nullable=False),
        sa.Column("ventilator_required", sa.Boolean(), nullable=False),
        sa.Column("arrival_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("discharged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="WAITING", nullable=False),
        sa.CheckConstraint("status IN ('WAITING', 'ADMITTED', 'DISCHARGED')", name="ck_encounters_status"),
        sa.CheckConstraint("discharged_at IS NULL OR admitted_at IS NULL OR discharged_at >= admitted_at", name="ck_encounters_discharge_after_admit"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.patient_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("encounter_id"),
    )
    op.create_index("ix_encounters_patient_status", "encounters", ["patient_id", "status"])

    op.create_table(
        "bed_assignments",
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("encounter_id", sa.Integer(), nullable=False),
        sa.Column("bed_id", sa.String(length=10), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.Integer(), nullable=True),
        sa.Column("release_reason", sa.String(length=100), nullable=True),
        sa.CheckConstraint("released_at IS NULL OR released_at >= assigned_at", name="ck_bed_assignment_release_after_assign"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["bed_id"], ["beds.bed_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.encounter_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_index("ix_bed_assignments_encounter", "bed_assignments", ["encounter_id"])
    op.create_index("ix_bed_assignments_bed", "bed_assignments", ["bed_id"])
    op.create_index("uq_bed_assignments_active_bed", "bed_assignments", ["bed_id"], unique=True, postgresql_where=sa.text("released_at IS NULL"), sqlite_where=sa.text("released_at IS NULL"))
    op.create_index("uq_bed_assignments_active_encounter", "bed_assignments", ["encounter_id"], unique=True, postgresql_where=sa.text("released_at IS NULL"), sqlite_where=sa.text("released_at IS NULL"))

    op.create_table(
        "equipment_assignments",
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("encounter_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.String(length=10), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.Integer(), nullable=True),
        sa.Column("release_reason", sa.String(length=100), nullable=True),
        sa.CheckConstraint("released_at IS NULL OR released_at >= assigned_at", name="ck_equipment_assignment_release_after_assign"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.equipment_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.encounter_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_index("ix_equipment_assignments_encounter", "equipment_assignments", ["encounter_id"])
    op.create_index("ix_equipment_assignments_equipment", "equipment_assignments", ["equipment_id"])
    op.create_index("uq_equipment_assignments_active_equipment", "equipment_assignments", ["equipment_id"], unique=True, postgresql_where=sa.text("released_at IS NULL"), sqlite_where=sa.text("released_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_equipment_assignments_active_equipment", table_name="equipment_assignments")
    op.drop_index("ix_equipment_assignments_equipment", table_name="equipment_assignments")
    op.drop_index("ix_equipment_assignments_encounter", table_name="equipment_assignments")
    op.drop_table("equipment_assignments")
    op.drop_index("uq_bed_assignments_active_encounter", table_name="bed_assignments")
    op.drop_index("uq_bed_assignments_active_bed", table_name="bed_assignments")
    op.drop_index("ix_bed_assignments_bed", table_name="bed_assignments")
    op.drop_index("ix_bed_assignments_encounter", table_name="bed_assignments")
    op.drop_table("bed_assignments")
    op.drop_index("ix_encounters_patient_status", table_name="encounters")
    op.drop_table("encounters")
