import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# ---------------------------------------------------------------------------
# Database URL selection
# ---------------------------------------------------------------------------
# If a full POSTGRES_USER env-var is present, connect to PostgreSQL.
# Otherwise fall back to a local SQLite file so the app works out-of-the-box
# on developer machines without a running Postgres instance.
# ---------------------------------------------------------------------------

_pg_user = os.getenv("POSTGRES_USER")

if _pg_user:
    from sqlalchemy import URL as _URL

    DATABASE_URL = _URL.create(
        "postgresql+psycopg2",
        username=_pg_user,
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "caregrid"),
    )
    _connect_args: dict = {}
else:
    # Resolve the SQLite file relative to the repository root so it is
    # always found regardless of the current working directory.
    _repo_root = Path(__file__).resolve().parents[2]
    _sqlite_path = _repo_root / "caregrid.db"
    DATABASE_URL = f"sqlite:///{_sqlite_path}"
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()