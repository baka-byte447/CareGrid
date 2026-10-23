"""Fixtures that run the REAL FastAPI app against an in-memory SQLite database
seeded from data/synthetic (no PostgreSQL needed). Skipped automatically on
machines that don't have the backend dependencies installed."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("psycopg2")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient                      # noqa: E402
from sqlalchemy import create_engine                           # noqa: E402
from sqlalchemy.orm import sessionmaker                        # noqa: E402
from sqlalchemy.pool import StaticPool                         # noqa: E402

DATA_DIR = str(ROOT / "data" / "synthetic")


@pytest.fixture()
def db_session(monkeypatch):
    from backend import import_data
    from backend.db.database import Base
    import backend.models  # noqa: F401  (registers the tables)

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
    from backend.models import Bed, Equipment
    session.query(Bed).update({Bed.status: "AVAILABLE"})
    session.query(Equipment).update({Equipment.status: "AVAILABLE"})
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    from backend.api.main import app
    from backend.db.database import get_db

    app.dependency_overrides[get_db] = lambda: (yield db_session)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
