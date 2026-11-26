"""Store incoming FHIR resources, telemetry and recommendation rationale."""
from alembic import op
import sqlalchemy as sa

revision = "18db403bf210"
down_revision = "f2a7c9d18430"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("surge_simulation_runs", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("parameters", sa.JSON(), nullable=False), sa.Column("operations", sa.JSON(), nullable=False))
    op.create_table("fhir_resources", sa.Column("reference", sa.String(80), primary_key=True),
                    sa.Column("local_id", sa.String(64), nullable=False),
                    sa.Column("resource", sa.JSON(), nullable=False))
    op.create_table("telemetry_records", sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("encounter_id", sa.Integer(), sa.ForeignKey("encounters.encounter_id"), nullable=False),
                    sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("observations", sa.JSON(), nullable=False),
                    sa.Column("score", sa.Integer(), nullable=False), sa.Column("risk", sa.String(20), nullable=False),
                    sa.Column("transfer_requested", sa.Boolean(), nullable=False))
    op.create_index("ix_telemetry_records_encounter_id", "telemetry_records", ["encounter_id"])
    op.add_column("encounters", sa.Column("clinical_risk", sa.String(20)))
    op.add_column("allocation_recommendations", sa.Column("explanation", sa.JSON()))


def downgrade():
    op.drop_column("allocation_recommendations", "explanation")
    op.drop_column("encounters", "clinical_risk")
    op.drop_table("telemetry_records")
    op.drop_table("fhir_resources")
    op.drop_table("surge_simulation_runs")
