"""
One-shot reconciliation utility — Milestone 2C.

Backfills ``Encounter`` rows for patients that were imported before Encounters
existed (i.e. before the Milestone 2C import_data.py update).

Usage::

    cd <project-root>
    python -m backend.reconcile_encounters

What it does
------------
1. For every ``Patient`` with ``current_status == "WAITING"`` that has **no**
   open Encounter (status IN ('WAITING', 'ADMITTED')), creates a ``WAITING``
   Encounter so that subsequent lifecycle-API calls can operate normally.

2. Skips ADMITTED and DISCHARGED patients — we cannot safely fabricate
   BedAssignment history for them (see migration c41a7d9e2b60).

3. Logs a warning for each OCCUPIED bed that still lacks a BedAssignment so
   operators know which beds remain outside the lifecycle.

This script is idempotent: running it twice will not create duplicate Encounters.
"""
import logging
from sqlalchemy import exists, select

from backend.db.database import SessionLocal
from backend.models.patient import Patient
from backend.models.bed import Bed
from backend.models.bed_assignment import BedAssignment
from backend.models.encounter import Encounter

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def reconcile(db) -> dict:
    """Create missing WAITING Encounters and report orphaned OCCUPIED beds."""

    # --- 1. Backfill WAITING Encounters ---
    # Subquery: patients that already have an open (WAITING or ADMITTED) Encounter
    has_open_encounter = (
        select(Encounter.patient_id)
        .where(Encounter.status.in_(["WAITING", "ADMITTED"]))
        .scalar_subquery()
    )

    patients_needing_encounter = (
        db.query(Patient)
        .filter(
            Patient.current_status == "WAITING",
            ~Patient.patient_id.in_(has_open_encounter),
        )
        .all()
    )

    created = 0
    for patient in patients_needing_encounter:
        enc = Encounter(
            patient_id=patient.patient_id,
            acuity=patient.acuity,
            specialty=patient.specialty,
            predicted_los=patient.predicted_los,
            isolation_required=patient.isolation_required,
            ventilator_required=patient.ventilator_required,
            arrival_time=patient.arrival_time,
            status="WAITING",
        )
        db.add(enc)
        created += 1

    if created:
        log.info("Created %d WAITING Encounter(s) for previously-unreconciled patients.", created)
    else:
        log.info("No unreconciled WAITING patients found — nothing to do.")

    # --- 2. Warn about OCCUPIED beds without a BedAssignment ---
    # Find bed_ids that have at least one open BedAssignment (released_at IS NULL)
    occupied_beds_with_assignment = (
        select(BedAssignment.bed_id)
        .where(BedAssignment.released_at.is_(None))
        .scalar_subquery()
    )

    orphan_beds = (
        db.query(Bed.bed_id)
        .filter(
            Bed.status == "OCCUPIED",
            ~Bed.bed_id.in_(occupied_beds_with_assignment),
        )
        .all()
    )

    orphan_count = len(orphan_beds)
    if orphan_count:
        log.warning(
            "%d OCCUPIED bed(s) have no BedAssignment row and cannot be discharged "
            "via the lifecycle API: %s%s",
            orphan_count,
            ", ".join(r[0] for r in orphan_beds[:10]),
            f", … (+{orphan_count - 10} more)" if orphan_count > 10 else "",
        )
    else:
        log.info("All OCCUPIED beds have matching BedAssignment rows.")

    db.commit()
    return {"encounters_created": created, "orphan_beds": orphan_count}


def main():
    db = SessionLocal()
    try:
        result = reconcile(db)
        log.info("Reconciliation complete: %s", result)
    except Exception as exc:
        db.rollback()
        log.error("Reconciliation failed: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
