"""allow bed-scoped audit events without patient attribution

Revision ID: f2a7c9d18430
Revises: e92d6c41b7a0
"""
from alembic import op
import sqlalchemy as sa

revision = "f2a7c9d18430"
down_revision = "e92d6c41b7a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column("patient_id", existing_type=sa.String(length=10), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    has_unassociated_audit = bind.execute(
        sa.text("SELECT 1 FROM audit_logs WHERE patient_id IS NULL LIMIT 1")
    ).first()
    if has_unassociated_audit is not None:
        raise RuntimeError(
            "Downgrade blocked: audit_logs contains NULL patient_id records; "
            "preserving audit history requires resolving them before downgrade."
        )
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column("patient_id", existing_type=sa.String(length=10), nullable=False)
