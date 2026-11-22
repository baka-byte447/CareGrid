"""create users table

Revision ID: e3d8f1c49b20
Revises: 80e696441929
Create Date: 2026-11-22 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3d8f1c49b20'
down_revision: Union[str, Sequence[str], None] = '80e696441929'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MARKER_TABLE = "_alembic_users_created_by_migration"


def _create_users_table() -> None:
    """Create the users table, its indexes, and the tracking marker table."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Marker table tracks that this migration created 'users', so downgrade
    # only drops 'users' if it was created here rather than pre-existing.
    op.create_table(
        MARKER_TABLE,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def _drop_users_table(inspector: Union[sa.engine.reflection.Inspector, None] = None) -> None:
    """Drop the users table, indexes, and tracking marker table."""
    if inspector is not None:
        existing_indexes = {idx['name'] for idx in inspector.get_indexes('users')}
        if op.f('ix_users_email') in existing_indexes:
            op.drop_index(op.f('ix_users_email'), table_name='users')
        if op.f('ix_users_username') in existing_indexes:
            op.drop_index(op.f('ix_users_username'), table_name='users')
        if op.f('ix_users_id') in existing_indexes:
            op.drop_index(op.f('ix_users_id'), table_name='users')
    else:
        op.drop_index(op.f('ix_users_email'), table_name='users')
        op.drop_index(op.f('ix_users_username'), table_name='users')
        op.drop_index(op.f('ix_users_id'), table_name='users')

    op.drop_table('users')
    op.drop_table(MARKER_TABLE)


def validate_existing_users_table(inspector: sa.engine.reflection.Inspector) -> None:
    """Validate that an existing 'users' table matches the User model schema.

    Checks:
    - All expected columns exist.
    - Expected columns are NOT NULL.
    - Column data types are compatible.
    - String column lengths are sufficient.
    - Primary key constraint is on ['id'].
    - Uniqueness is enforced on 'username' and 'email'.
    - 'created_at' has timezone=True where supported by the database dialect.

    Raises:
        ValueError: If any check fails.
    """
    cols = {c["name"]: c for c in inspector.get_columns("users")}

    expected_columns = {
        "id": {"types": (sa.Integer,), "min_length": None},
        "username": {"types": (sa.String,), "min_length": 50},
        "email": {"types": (sa.String,), "min_length": 255},
        "hashed_password": {"types": (sa.String,), "min_length": 255},
        "role": {"types": (sa.String,), "min_length": 30},
        "is_active": {"types": (sa.Boolean,), "min_length": None},
        "created_at": {"types": (sa.DateTime, sa.TIMESTAMP), "min_length": None},
    }

    # 1. Check for missing columns
    missing_cols = set(expected_columns.keys()) - set(cols.keys())
    if missing_cols:
        raise ValueError(
            f"Existing 'users' table is incompatible: missing required column(s): "
            f"{', '.join(sorted(missing_cols))}"
        )

    # 2. Check primary key constraint first
    pk = inspector.get_pk_constraint("users")
    constrained_pk = pk.get("constrained_columns") or []
    if constrained_pk != ["id"]:
        raise ValueError(
            f"Existing 'users' table is incompatible: primary key must be ['id'], got {constrained_pk}"
        )

    # 3. Check nullability, types, and lengths
    for col_name, spec in expected_columns.items():
        col = cols[col_name]
        # In SQLite, an INTEGER PRIMARY KEY column without explicit NOT NULL may reflect
        # as nullable=True even though it acts as the primary key rowid.
        if col.get("nullable") is True and col_name != "id":
            raise ValueError(
                f"Existing 'users' table is incompatible: column '{col_name}' must be NOT NULL"
            )
        col_type = col["type"]
        if not isinstance(col_type, spec["types"]):
            expected_type_names = "/".join(t.__name__ for t in spec["types"])
            raise ValueError(
                f"Existing 'users' table is incompatible: column '{col_name}' has type "
                f"'{col_type}', expected {expected_type_names}"
            )
        min_length = spec["min_length"]
        if min_length is not None and hasattr(col_type, "length") and col_type.length is not None:
            if col_type.length < min_length:
                raise ValueError(
                    f"Existing 'users' table is incompatible: column '{col_name}' length "
                    f"({col_type.length}) is less than required minimum ({min_length})"
                )

    # 4. Check uniqueness on username and email
    unique_columns = set()
    for uc in inspector.get_unique_constraints("users"):
        col_names = uc.get("column_names") or []
        if len(col_names) == 1:
            unique_columns.add(col_names[0])

    for idx in inspector.get_indexes("users"):
        if idx.get("unique"):
            col_names = idx.get("column_names") or []
            if len(col_names) == 1:
                unique_columns.add(col_names[0])

    for col_name in ("username", "email"):
        if col_name not in unique_columns:
            raise ValueError(
                f"Existing 'users' table is incompatible: column '{col_name}' must have a unique constraint or index"
            )

    # 5. Check created_at timezone configuration where supported by the database dialect
    dialect_name = getattr(inspector.dialect, "name", "")
    if dialect_name != "sqlite":
        created_at_col = cols["created_at"]
        created_at_type = created_at_col["type"]
        if not getattr(created_at_type, "timezone", False):
            raise ValueError(
                "Existing 'users' table is incompatible: column 'created_at' must have timezone=True"
            )


def upgrade() -> None:
    """Upgrade schema."""
    if context.is_offline_mode():
        _create_users_table()
    else:
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        tables = inspector.get_table_names()
        if 'users' not in tables:
            _create_users_table()
        else:
            # Table already exists: validate its schema against the User model
            validate_existing_users_table(inspector)

            # Ensure expected non-unique indexes exist if not already present
            existing_indexes = {idx['name'] for idx in inspector.get_indexes('users')}
            if op.f('ix_users_id') not in existing_indexes:
                op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    if context.is_offline_mode():
        raise RuntimeError(
            "Offline downgrade is not supported for revision e3d8f1c49b20. "
            "Determining whether the 'users' table was created by this migration or "
            "pre-existed requires online database inspection to safely prevent accidental data loss."
        )

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    # Only drop the users table if it was created by this migration
    if MARKER_TABLE in tables:
        _drop_users_table(inspector)
    # If MARKER_TABLE is not present, the users table pre-existed before this migration.
    # Preserve the table and its existing data without dropping anything.
