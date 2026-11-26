"""add allocation recommendation decision tracking

Revision ID: e92d6c41b7a0
Revises: d7f4c2a91e63
Create Date: 2026-11-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e92d6c41b7a0"
down_revision: Union[str, Sequence[str], None] = "d7f4c2a91e63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("allocation_recommendations") as batch_op:
        batch_op.add_column(sa.Column("decision_status", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("decision_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("decided_by", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_allocation_recommendations_decided_by_users",
            "users",
            ["decided_by"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_allocation_recommendations_decision_status_decided_at",
        "allocation_recommendations",
        ["decision_status", "decided_at"],
    )
    op.create_index(
        "ix_allocation_recommendations_decided_by",
        "allocation_recommendations",
        ["decided_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_allocation_recommendations_decided_by", table_name="allocation_recommendations")
    op.drop_index(
        "ix_allocation_recommendations_decision_status_decided_at",
        table_name="allocation_recommendations",
    )
    with op.batch_alter_table("allocation_recommendations") as batch_op:
        batch_op.drop_constraint(
            "fk_allocation_recommendations_decided_by_users",
            type_="foreignkey",
        )
        batch_op.drop_column("decided_at")
        batch_op.drop_column("decided_by")
        batch_op.drop_column("decision_reason")
        batch_op.drop_column("decision_status")
