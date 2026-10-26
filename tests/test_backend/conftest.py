"""Fixtures that run the REAL FastAPI app against an in-memory SQLite database
seeded from data/synthetic (no PostgreSQL needed).

If the backend dependencies are not installed (pip install -r requirements-dev.txt)
this whole folder is skipped, and the pytest header says so, instead of breaking
the rest of the test suite."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = str(ROOT / "data" / "synthetic")

_REQUIRED = ("fastapi", "httpx", "psycopg2", "sqlalchemy")
_MISSING = [m for m in _REQUIRED if importlib.util.find_spec(m) is None]

if _MISSING:
    collect_ignore_glob = ["test_*.py"]      # nothing in this folder is collected


def pytest_report_header(config):
    if _MISSING:
        return (f"backend API tests SKIPPED - missing packages: {', '.join(_MISSING)} "
                f"(pip install -r requirements-dev.txt)")


@pytest.fixture()
def db_session(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend import import_data
    from backend.db.database import Base
    import backend.models  # noqa: F401  (registers the tables)
    from backend.models import Bed, Equipment

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()

    monkeypatch.setattr(import_data, "DATA_DIR", DATA_DIR)
    import_data.import_patients(session)
    import_data.import_beds(session)
    import_data.import_staff(session)
    import_data.import_equipment(session)
    session.commit()

    # start from an empty hospital (the CSV snapshot marks ~65% of beds occupied)
    session.query(Bed).update({Bed.status: "AVAILABLE"})
    session.query(Equipment).update({Equipment.status: "AVAILABLE"})
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    from backend.api.main import app
    from backend.db.database import get_db

    app.dependency_overrides[get_db] = lambda: (yield db_session)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
