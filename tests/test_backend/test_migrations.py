import os
import tempfile
import importlib.util
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
from alembic.config import Config
from alembic import command
import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql

from backend.db.database import Base, DATABASE_URL
from backend.models.user import User  # Ensure User model is loaded into Base.metadata


def _load_users_migration_module():
    """Dynamically load the e3d8f1c49b20_create_users_table migration module."""
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "e3d8f1c49b20_create_users_table.py"
    )
    spec = importlib.util.spec_from_file_location("e3d8f1c49b20_create_users_table", migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def temp_alembic_db():
    """Create a temporary SQLite database for isolated Alembic migration testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db_url = f"sqlite:///{db_path}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    yield cfg, db_url

    # Cleanup after test
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_fresh_database_upgrade_and_downgrade(temp_alembic_db):
    """Verify fresh database upgrade to head creates all tables (including users and marker),
    and downgrade drops users and marker without affecting other tables.
    """
    cfg, db_url = temp_alembic_db

    # 1. Upgrade to head on a fresh database
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    expected_tables = {
        "alembic_version",
        "audit_logs",
        "beds",
        "equipment",
        "patients",
        "staff",
        "users",
        "_alembic_users_created_by_migration",
    }
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

    # Verify users columns
    user_cols = {c["name"]: c for c in insp.get_columns("users")}
    for col_name in ["id", "username", "email", "hashed_password", "role", "is_active", "created_at"]:
        assert col_name in user_cols, f"Missing column {col_name} on users table"
        assert not user_cols[col_name]["nullable"], f"Column {col_name} should not be nullable"

    # Verify users indexes
    user_indexes = {i["name"]: i for i in insp.get_indexes("users")}
    assert "ix_users_id" in user_indexes
    assert "ix_users_username" in user_indexes
    assert "ix_users_email" in user_indexes

    # 2. Downgrade by 1 revision
    engine.dispose()
    command.downgrade(cfg, "-1")

    engine = create_engine(db_url)
    insp = inspect(engine)
    tables_after_downgrade = set(insp.get_table_names())

    assert "users" not in tables_after_downgrade, "users table was not dropped on downgrade of fresh migration"
    assert "_alembic_users_created_by_migration" not in tables_after_downgrade, "marker table was not dropped"
    assert {"beds", "equipment", "patients", "staff", "audit_logs"}.issubset(tables_after_downgrade), (
        "Other tables must remain intact after downgrade"
    )

    # 3. Upgrade back to head re-creates users and marker
    engine.dispose()
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    insp = inspect(engine)
    assert "users" in insp.get_table_names()
    assert "_alembic_users_created_by_migration" in insp.get_table_names()
    engine.dispose()


def test_offline_downgrade_fails_safely(temp_alembic_db):
    """Verify that offline downgrade fails safely with RuntimeError explaining online inspection is required."""
    cfg, _ = temp_alembic_db
    with pytest.raises(
        RuntimeError, match="Offline downgrade is not supported for revision e3d8f1c49b20"
    ):
        command.downgrade(cfg, "e3d8f1c49b20:80e696441929", sql=True)


def test_existing_compatible_users_table(temp_alembic_db):
    """Verify that if a compatible users table already exists prior to migration,
    upgrade succeeds, does not duplicate the table, does not create the marker table,
    and preserves existing data.
    """
    cfg, db_url = temp_alembic_db

    # 1. Upgrade up to the revision right before users migration
    command.upgrade(cfg, "80e696441929")

    # 2. Pre-create a compatible users table (e.g. simulating create_tables.py)
    engine = create_engine(db_url)
    Base.metadata.tables["users"].create(engine)

    # Insert a user record prior to migration
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, username, email, hashed_password, role, is_active, created_at) "
                "VALUES (:id, :username, :email, :hashed_password, :role, :is_active, :created_at)"
            ),
            {
                "id": 1,
                "username": "existing_admin",
                "email": "admin@hospital.org",
                "hashed_password": "hashed_secret_123",
                "role": "admin",
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
            },
        )
    engine.dispose()

    # 3. Run migration to head
    command.upgrade(cfg, "head")

    # 4. Verify migration succeeded and did NOT create the marker table
    engine = create_engine(db_url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "users" in tables
    assert "_alembic_users_created_by_migration" not in tables, (
        "Marker table should NOT be created for a pre-existing users table"
    )

    # Verify existing data is preserved
    with engine.connect() as conn:
        result = conn.execute(text("SELECT username, email, role FROM users WHERE id = 1")).mappings().one()
        assert result["username"] == "existing_admin"
        assert result["email"] == "admin@hospital.org"
        assert result["role"] == "admin"
    engine.dispose()


def test_existing_incompatible_users_table_missing_column(temp_alembic_db):
    """Verify that an existing users table missing required columns raises ValueError."""
    cfg, db_url = temp_alembic_db

    # Upgrade to parent revision
    command.upgrade(cfg, "80e696441929")

    # Create incompatible users table missing email and hashed_password
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "  id INTEGER PRIMARY KEY,"
                "  username VARCHAR(50) NOT NULL UNIQUE,"
                "  role VARCHAR(30) NOT NULL"
                ")"
            )
        )
    engine.dispose()

    # Upgrade must fail with a clear error
    with pytest.raises(ValueError, match="missing required column"):
        command.upgrade(cfg, "head")


def test_existing_incompatible_users_table_wrong_type(temp_alembic_db):
    """Verify that an existing users table with an invalid column type raises ValueError."""
    cfg, db_url = temp_alembic_db

    command.upgrade(cfg, "80e696441929")

    # Create users table with role as INTEGER instead of VARCHAR/String
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "  id INTEGER NOT NULL PRIMARY KEY,"
                "  username VARCHAR(50) NOT NULL UNIQUE,"
                "  email VARCHAR(255) NOT NULL UNIQUE,"
                "  hashed_password VARCHAR(255) NOT NULL,"
                "  role INTEGER NOT NULL,"
                "  is_active BOOLEAN NOT NULL,"
                "  created_at DATETIME NOT NULL"
                ")"
            )
        )
    engine.dispose()

    with pytest.raises(ValueError, match="Existing 'users' table is incompatible: column 'role' has type"):
        command.upgrade(cfg, "head")


def test_existing_incompatible_users_table_nullable_column(temp_alembic_db):
    """Verify that an existing users table with a nullable column where NOT NULL is required raises ValueError."""
    cfg, db_url = temp_alembic_db

    command.upgrade(cfg, "80e696441929")

    # Create users table where email is nullable
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "  id INTEGER NOT NULL PRIMARY KEY,"
                "  username VARCHAR(50) NOT NULL UNIQUE,"
                "  email VARCHAR(255) NULL UNIQUE,"
                "  hashed_password VARCHAR(255) NOT NULL,"
                "  role VARCHAR(30) NOT NULL,"
                "  is_active BOOLEAN NOT NULL,"
                "  created_at DATETIME NOT NULL"
                ")"
            )
        )
    engine.dispose()

    with pytest.raises(ValueError, match="Existing 'users' table is incompatible: column 'email' must be NOT NULL"):
        command.upgrade(cfg, "head")


def test_existing_incompatible_users_table_missing_unique_constraint(temp_alembic_db):
    """Verify that an existing users table without unique constraints on username/email raises ValueError."""
    cfg, db_url = temp_alembic_db

    command.upgrade(cfg, "80e696441929")

    # Create users table without unique constraint on username
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "  id INTEGER NOT NULL PRIMARY KEY,"
                "  username VARCHAR(50) NOT NULL,"
                "  email VARCHAR(255) NOT NULL UNIQUE,"
                "  hashed_password VARCHAR(255) NOT NULL,"
                "  role VARCHAR(30) NOT NULL,"
                "  is_active BOOLEAN NOT NULL,"
                "  created_at DATETIME NOT NULL"
                ")"
            )
        )
    engine.dispose()

    with pytest.raises(
        ValueError, match="Existing 'users' table is incompatible: column 'username' must have a unique constraint or index"
    ):
        command.upgrade(cfg, "head")


def test_existing_incompatible_users_table_wrong_pk(temp_alembic_db):
    """Verify that an existing users table with incorrect primary key raises ValueError."""
    cfg, db_url = temp_alembic_db

    command.upgrade(cfg, "80e696441929")

    # Create users table with username as primary key
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "  id INTEGER NOT NULL,"
                "  username VARCHAR(50) PRIMARY KEY,"
                "  email VARCHAR(255) NOT NULL UNIQUE,"
                "  hashed_password VARCHAR(255) NOT NULL,"
                "  role VARCHAR(30) NOT NULL,"
                "  is_active BOOLEAN NOT NULL,"
                "  created_at DATETIME NOT NULL"
                ")"
            )
        )
    engine.dispose()

    with pytest.raises(ValueError, match="primary key must be \\['id'\\]"):
        command.upgrade(cfg, "head")


def test_existing_incompatible_users_table_short_length(temp_alembic_db):
    """Verify that an existing users table with insufficient column length raises ValueError."""
    cfg, db_url = temp_alembic_db

    command.upgrade(cfg, "80e696441929")

    # Create users table with username length only 10 chars (expected at least 50)
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE users ("
                "  id INTEGER NOT NULL PRIMARY KEY,"
                "  username VARCHAR(10) NOT NULL UNIQUE,"
                "  email VARCHAR(255) NOT NULL UNIQUE,"
                "  hashed_password VARCHAR(255) NOT NULL,"
                "  role VARCHAR(30) NOT NULL,"
                "  is_active BOOLEAN NOT NULL,"
                "  created_at DATETIME NOT NULL"
                ")"
            )
        )
    engine.dispose()

    with pytest.raises(ValueError, match="column 'username' length .* is less than required minimum"):
        command.upgrade(cfg, "head")


def test_existing_incompatible_users_table_timezone():
    """Verify that an existing users table with an incompatible timezone configuration
    (e.g. TIMESTAMP WITHOUT TIME ZONE) is rejected where the database dialect supports checking it.
    """
    migration_mod = _load_users_migration_module()

    # 1. Dialect reflection test: Mock an inspector for PostgreSQL with timezone=False on created_at
    mock_insp = MagicMock()
    mock_insp.dialect.name = "postgresql"
    mock_insp.get_columns.return_value = [
        {"name": "id", "type": sa.Integer(), "nullable": False},
        {"name": "username", "type": sa.String(50), "nullable": False},
        {"name": "email", "type": sa.String(255), "nullable": False},
        {"name": "hashed_password", "type": sa.String(255), "nullable": False},
        {"name": "role", "type": sa.String(30), "nullable": False},
        {"name": "is_active", "type": sa.Boolean(), "nullable": False},
        {"name": "created_at", "type": postgresql.TIMESTAMP(timezone=False), "nullable": False},
    ]
    mock_insp.get_pk_constraint.return_value = {"constrained_columns": ["id"]}
    mock_insp.get_unique_constraints.return_value = [{"column_names": ["username"]}, {"column_names": ["email"]}]
    mock_insp.get_indexes.return_value = []

    with pytest.raises(ValueError, match="column 'created_at' must have timezone=True"):
        migration_mod.validate_existing_users_table(mock_insp)

    # 2. Live database test: If PostgreSQL is reachable, test against a real PostgreSQL table
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            pass
    except Exception:
        # If live PostgreSQL is not reachable, dialect test above provides full coverage
        return

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(
                text(
                    "CREATE TEMP TABLE users ("
                    "  id SERIAL PRIMARY KEY,"
                    "  username VARCHAR(50) NOT NULL UNIQUE,"
                    "  email VARCHAR(255) NOT NULL UNIQUE,"
                    "  hashed_password VARCHAR(255) NOT NULL,"
                    "  role VARCHAR(30) NOT NULL,"
                    "  is_active BOOLEAN NOT NULL,"
                    "  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL"
                    ")"
                )
            )
            insp = inspect(conn)
            with pytest.raises(ValueError, match="column 'created_at' must have timezone=True"):
                migration_mod.validate_existing_users_table(insp)
        finally:
            trans.rollback()
    engine.dispose()


def test_downgrade_preserves_pre_existing_users_table_and_data(temp_alembic_db):
    """Verify that downgrade does NOT drop or delete data from a pre-existing users table."""
    cfg, db_url = temp_alembic_db

    # 1. Upgrade to revision prior to users migration
    command.upgrade(cfg, "80e696441929")

    # 2. Pre-create compatible users table and insert records
    engine = create_engine(db_url)
    Base.metadata.tables["users"].create(engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, username, email, hashed_password, role, is_active, created_at) "
                "VALUES (:id, :username, :email, :hashed_password, :role, :is_active, :created_at)"
            ),
            [
                {
                    "id": 1,
                    "username": "pre_existing_admin",
                    "email": "admin@hospital.org",
                    "hashed_password": "hash1",
                    "role": "admin",
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc),
                },
                {
                    "id": 2,
                    "username": "pre_existing_doctor",
                    "email": "doctor@hospital.org",
                    "hashed_password": "hash2",
                    "role": "doctor",
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc),
                },
            ],
        )
    engine.dispose()

    # 3. Upgrade to head
    command.upgrade(cfg, "head")

    # 4. Downgrade by 1 revision
    command.downgrade(cfg, "-1")

    # 5. Verify the pre-existing users table was NOT dropped and data is completely intact
    engine = create_engine(db_url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "users" in tables, "Pre-existing users table was erroneously dropped during downgrade!"

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, username, email, role FROM users ORDER BY id")).mappings().all()
        assert len(rows) == 2, f"Expected 2 user records, got {len(rows)}"
        assert rows[0]["username"] == "pre_existing_admin"
        assert rows[1]["username"] == "pre_existing_doctor"

    engine.dispose()
