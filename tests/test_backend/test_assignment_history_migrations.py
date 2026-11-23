"""Isolated migration and integrity tests for encounter assignment history."""
from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


@pytest.fixture(autouse=True)
def enable_sqlite_foreign_keys():
    """Enable FK enforcement on every SQLite connection used by these tests."""
    def _set_foreign_keys(dbapi_connection, connection_record):
        if dbapi_connection.__class__.__module__ == "sqlite3":
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    event.listen(Engine, "connect", _set_foreign_keys)
    yield
    event.remove(Engine, "connect", _set_foreign_keys)


@pytest.fixture
def migrated_db(tmp_path):
    db_path = tmp_path / "assignment_history.db"
    url = f"sqlite:///{db_path.as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    yield engine, cfg
    engine.dispose()


def _seed(conn):
    conn.execute(text("INSERT INTO patients VALUES ('P1','adult',3,'General',2.0,0,0,:arrival,'WAITING')"), {"arrival": datetime.now(timezone.utc).replace(tzinfo=None)})
    conn.execute(text("INSERT INTO beds VALUES ('B1','WARD','North','AVAILABLE',0)"))
    conn.execute(text("INSERT INTO beds VALUES ('B2','WARD','North','AVAILABLE',0)"))
    conn.execute(text("INSERT INTO equipment VALUES ('E1','VENTILATOR','AVAILABLE','North')"))
    conn.execute(text("INSERT INTO users (username,email,hashed_password,role,is_active,created_at) VALUES ('u','u@example.com','x','nurse',1,:now)"), {"now": datetime.now(timezone.utc).replace(tzinfo=None)})
    conn.execute(text("INSERT INTO encounters (patient_id,acuity,specialty,predicted_los,isolation_required,ventilator_required,arrival_time,status) VALUES ('P1',3,'General',2.0,0,1,:arrival,'ADMITTED')"), {"arrival": datetime.now(timezone.utc).replace(tzinfo=None)})


def test_fresh_upgrade_creates_tables_constraints_and_indexes(migrated_db):
    engine, _ = migrated_db
    insp = inspect(engine)
    assert {"encounters", "bed_assignments", "equipment_assignments"}.issubset(insp.get_table_names())
    assert {fk["referred_table"] for fk in insp.get_foreign_keys("encounters")} == {"patients"}
    assert {fk["referred_table"] for fk in insp.get_foreign_keys("bed_assignments")} == {"encounters", "beds", "users"}
    assert {fk["referred_table"] for fk in insp.get_foreign_keys("equipment_assignments")} == {"encounters", "equipment", "users"}
    assert "ix_encounters_patient_status" in {idx["name"] for idx in insp.get_indexes("encounters")}
    assert "uq_bed_assignments_active_bed" in {idx["name"] for idx in insp.get_indexes("bed_assignments")}
    assert "uq_bed_assignments_active_encounter" in {idx["name"] for idx in insp.get_indexes("bed_assignments")}
    assert "uq_equipment_assignments_active_equipment" in {idx["name"] for idx in insp.get_indexes("equipment_assignments")}


def test_assignment_history_and_active_uniqueness(migrated_db):
    engine, _ = migrated_db
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        _seed(conn)
        conn.execute(text("INSERT INTO bed_assignments (encounter_id,bed_id,assigned_at,assigned_by) VALUES (1,'B1',:now,1)"), {"now": now})
        conn.execute(text("INSERT INTO equipment_assignments (encounter_id,equipment_id,assigned_at,assigned_by) VALUES (1,'E1',:now,1)"), {"now": now})

    for table, resource, resource_id in [("bed_assignments", "bed_id", "B2"), ("equipment_assignments", "equipment_id", "E1")]:
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text(f"INSERT INTO {table} (encounter_id,{resource},assigned_at) VALUES (1,:resource,:now)"), {"resource": resource_id, "now": now})

    with engine.begin() as conn:
        conn.execute(text("UPDATE bed_assignments SET released_at=:released, release_reason='transfer' WHERE assignment_id=1"), {"released": now + timedelta(minutes=10)})
        conn.execute(text("INSERT INTO bed_assignments (encounter_id,bed_id,assigned_at) VALUES (1,'B2',:now)"), {"now": now + timedelta(minutes=10)})
        conn.execute(text("UPDATE equipment_assignments SET released_at=:released, release_reason='discharge' WHERE assignment_id=1"), {"released": now + timedelta(minutes=10)})
        conn.execute(text("INSERT INTO equipment_assignments (encounter_id,equipment_id,assigned_at) VALUES (1,'E1',:now)"), {"now": now + timedelta(minutes=10)})
        assert conn.execute(text("SELECT COUNT(*) FROM bed_assignments WHERE encounter_id=1")).scalar_one() == 2
        assert conn.execute(text("SELECT COUNT(*) FROM equipment_assignments WHERE encounter_id=1")).scalar_one() == 2


def test_foreign_keys_and_check_constraints(migrated_db):
    engine, _ = migrated_db
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        _seed(conn)
    for sql, params in [
        ("INSERT INTO encounters (patient_id,acuity,specialty,predicted_los,isolation_required,ventilator_required,arrival_time,status) VALUES ('missing',1,'x',1,0,0,:n,'WAITING')", {"n": now}),
        ("INSERT INTO bed_assignments (encounter_id,bed_id,assigned_at) VALUES (99,'B1',:n)", {"n": now}),
        ("INSERT INTO equipment_assignments (encounter_id,equipment_id,assigned_at) VALUES (1,'missing',:n)", {"n": now}),
        ("INSERT INTO bed_assignments (encounter_id,bed_id,assigned_at,assigned_by) VALUES (1,'B1',:n,99)", {"n": now}),
        ("INSERT INTO equipment_assignments (encounter_id,equipment_id,assigned_at,assigned_by) VALUES (1,'E1',:n,99)", {"n": now}),
        ("INSERT INTO encounters (patient_id,acuity,specialty,predicted_los,isolation_required,ventilator_required,arrival_time,status) VALUES ('P1',1,'x',1,0,0,:n,'UNKNOWN')", {"n": now}),
        ("INSERT INTO bed_assignments (encounter_id,bed_id,assigned_at,released_at) VALUES (1,'B1',:n,:before)", {"n": now, "before": now - timedelta(seconds=1)}),
    ]:
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(text(sql), params)


def test_legacy_resources_are_preserved_without_fabricated_assignments(tmp_path):
    db_path = tmp_path / "existing.db"
    url = f"sqlite:///{db_path.as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "e3d8f1c49b20")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO patients VALUES ('P1','adult',3,'General',2.0,0,0,:arrival,'WAITING')"), {"arrival": datetime.now(timezone.utc).replace(tzinfo=None)})
        conn.execute(text("INSERT INTO beds VALUES ('B1','WARD','North','OCCUPIED',0)"))
        conn.execute(text("INSERT INTO equipment VALUES ('E1','VENTILATOR','IN_USE','North')"))
        conn.execute(text("INSERT INTO users (username,email,hashed_password,role,is_active,created_at) VALUES ('u','u@example.com','x','nurse',1,:now)"), {"now": datetime.now(timezone.utc).replace(tzinfo=None)})
    engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM patients")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM beds")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM equipment")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1
        assert conn.execute(text("SELECT status FROM beds WHERE bed_id='B1'")).scalar_one() == "OCCUPIED"
        assert conn.execute(text("SELECT status FROM equipment WHERE equipment_id='E1'")).scalar_one() == "IN_USE"
        assert conn.execute(text("SELECT COUNT(*) FROM encounters")).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM bed_assignments")).scalar_one() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM equipment_assignments")).scalar_one() == 0
    engine.dispose()

    # Seed lifecycle history after upgrade so downgrade's intentional deletion
    # of these new tables can be distinguished from preservation of legacy rows.
    engine = create_engine(url)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO encounters (patient_id,acuity,specialty,predicted_los,isolation_required,ventilator_required,arrival_time,admitted_at,status) VALUES ('P1',3,'General',2.0,0,1,:n,:n,'ADMITTED')"), {"n": now})
        conn.execute(text("INSERT INTO bed_assignments (encounter_id,bed_id,assigned_at) VALUES (1,'B1',:n)"), {"n": now})
        conn.execute(text("INSERT INTO equipment_assignments (encounter_id,equipment_id,assigned_at) VALUES (1,'E1',:n)"), {"n": now})
        assert conn.execute(text("SELECT COUNT(*) FROM encounters")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM bed_assignments")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM equipment_assignments")).scalar_one() == 1
    engine.dispose()

    # Downgrading intentionally deletes lifecycle history and its tables.
    command.downgrade(cfg, "e3d8f1c49b20")
    engine = create_engine(url)
    insp = inspect(engine)
    assert not {"encounters", "bed_assignments", "equipment_assignments"} & set(insp.get_table_names())
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM patients")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM beds")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM equipment")).scalar_one() == 1
        assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1
        assert conn.execute(text("SELECT status FROM beds WHERE bed_id='B1'")).scalar_one() == "OCCUPIED"
        assert conn.execute(text("SELECT status FROM equipment WHERE equipment_id='E1'")).scalar_one() == "IN_USE"
    engine.dispose()
