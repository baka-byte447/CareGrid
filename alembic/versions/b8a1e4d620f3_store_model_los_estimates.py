"""Store the LOS model estimate on recommendations and admissions."""

from alembic import op
import sqlalchemy as sa

revision = "b8a1e4d620f3"
down_revision = "18db403bf210"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("encounters", sa.Column("los_estimate_days", sa.Float(), nullable=True))
    op.add_column("allocation_recommendations", sa.Column("los_estimate_days", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("allocation_recommendations", "los_estimate_days")
    op.drop_column("encounters", "los_estimate_days")
