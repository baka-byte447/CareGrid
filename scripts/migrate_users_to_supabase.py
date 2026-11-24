"""One-time, transactional copy of users from local PostgreSQL to the configured DB.

Run with ``python -m scripts.migrate_users_to_supabase`` from the repository root.
The configured destination engine is selected by backend.db.database, so verify
its environment points to the intended Supabase database before running.
"""

import sys
from getpass import getpass

from sqlalchemy import URL, func, select, text
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import engine as destination_engine
from backend.models.user import User


EXPECTED_SOURCE_RECORDS = 8
USER_FIELDS = (
    "id",
    "username",
    "email",
    "hashed_password",
    "role",
    "is_active",
    "created_at",
)


class DestinationNotEmpty(Exception):
    def __init__(self, record_count: int):
        self.record_count = record_count


def _read_source_records(source_engine) -> list[dict]:
    # The server-side setting makes this source connection read-only as an
    # additional safeguard; the script performs SELECTs against this engine only.
    with Session(source_engine) as source_session:
        rows = source_session.execute(
            select(User).order_by(User.id)
        ).scalars().all()
        return [
            {field: getattr(row, field) for field in USER_FIELDS}
            for row in rows
        ]


def _transfer_and_verify(source_records: list[dict]) -> int:
    with destination_engine.begin() as connection:
        # Serialize competing import/write attempts around the emptiness check
        # and copy. The lock is released on commit or rollback.
        connection.execute(
            text("LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE")
        )

        destination_count = connection.execute(
            select(func.count()).select_from(User)
        ).scalar_one()
        if destination_count:
            raise DestinationNotEmpty(destination_count)

        connection.execute(User.__table__.insert(), source_records)

        expected = source_records
        actual_rows = connection.execute(
            select(*(getattr(User, field) for field in USER_FIELDS)).order_by(User.id)
        ).mappings().all()
        actual = [dict(row) for row in actual_rows]
        if actual != expected:
            raise RuntimeError("Destination verification did not match source records")

        max_id = max(record["id"] for record in source_records)
        sequence_name = connection.execute(
            text("SELECT pg_get_serial_sequence('public.users', 'id')")
        ).scalar_one_or_none()
        if sequence_name is None:
            raise RuntimeError("Could not locate the users ID sequence")

        # setval is not transactional in PostgreSQL. It is performed only after
        # row verification; the table lock prevents concurrent user inserts
        # while this transaction is active.
        connection.execute(
            text(
                "SELECT setval(CAST(:sequence_name AS regclass), :max_id, true)"
            ),
            {"sequence_name": sequence_name, "max_id": max_id},
        )

        return len(actual)


def main() -> int:
    destination_url = destination_engine.url
    destination_host = (destination_url.host or "").lower()
    if (
        not destination_host.endswith(".pooler.supabase.com")
        or destination_url.database != "postgres"
    ):
        print(
            "Transfer aborted: destination must use a .pooler.supabase.com "
            "host and the postgres database."
        )
        return 1

    source_password = getpass("Old local PostgreSQL password: ")
    source_url = URL.create(
        "postgresql+psycopg2",
        username="postgres",
        password=source_password,
        host="localhost",
        port=5432,
        database="caregrid",
    )

    source_engine = None
    try:
        source_engine = create_engine(
            source_url,
            connect_args={"options": "-c default_transaction_read_only=on"},
        )

        source_records = _read_source_records(source_engine)
        source_count = len(source_records)
        print(f"Source records: {source_count}")
        if source_count != EXPECTED_SOURCE_RECORDS:
            print(
                "Transfer aborted: source record count did not match the "
                f"expected {EXPECTED_SOURCE_RECORDS}. Final verification: NOT RUN."
            )
            return 1

        try:
            destination_count = _transfer_and_verify(source_records)
        except DestinationNotEmpty as exc:
            print(
                f"Destination records: {exc.record_count}; transfer aborted. "
                "Final verification: NOT RUN."
            )
            return 1

        print(f"Destination records: {destination_count}")
        for record in source_records:
            print(
                f"username={record['username']} role={record['role']} "
                f"active={record['is_active']}"
            )
        print(
            "Final verification: PASS "
            f"({destination_count} records matched across all seven fields)."
        )
        return 0
    except Exception:
        # Do not print exception details: database driver exceptions can include
        # bound SQL parameters, which include password hashes during insertion.
        print("Transfer failed. Final verification: FAIL.")
        return 1
    finally:
        if source_engine is not None:
            source_engine.dispose()
        destination_engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
