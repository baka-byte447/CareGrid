"""Transactional operations for Encounter and resource assignment history.

These functions add and flush changes but never commit. The caller owns the
outer SQLAlchemy transaction and must commit on success or roll it back if an
operation raises. This keeps lifecycle changes atomic with any caller work.

Lock order is Patient, Encounter, Beds sorted by ID, then Equipment sorted by
ID. Resource assignment rows are read while their owning Encounter and resource
rows are locked; partial unique indexes guard concurrent active assignments.
SQLite does not provide PostgreSQL-equivalent row-lock behavior.
"""
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import (
    AuditLog,
    Bed,
    BedAssignment,
    Encounter,
    Equipment,
    EquipmentAssignment,
    Patient,
)
from simulator.hospital.allocation_rules import candidate_bed_types


class LifecycleError(Exception):
    """Base exception for rejected patient lifecycle operations."""


class LifecycleNotFound(LifecycleError):
    """A requested patient, encounter, bed, or equipment item does not exist."""


class LifecycleConflict(LifecycleError):
    """The requested operation conflicts with current lifecycle/resource state."""


class LifecycleValidationError(LifecycleError):
    """The requested resource or clinical attributes are incompatible."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _actor_id(actor_id: int | object | None) -> int | None:
    if actor_id is None or isinstance(actor_id, int):
        return actor_id
    value = getattr(actor_id, "id", None)
    if not isinstance(value, int):
        raise LifecycleValidationError("actor must be a user ID or a persisted User")
    return value


def _record(
    db: Session,
    encounter: Encounter,
    action: str,
    bed_id: str | None = None,
    algorithm: str = "lifecycle",
) -> None:
    db.add(AuditLog(
        patient_id=encounter.patient_id,
        bed_id=bed_id,
        action=action,
        algorithm=algorithm,
        timestamp=_now(),
    ))


def _lock_encounter(db: Session, encounter_id: int) -> Encounter:
    encounter = db.execute(
        select(Encounter)
        .where(Encounter.encounter_id == encounter_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if encounter is None:
        raise LifecycleNotFound("Encounter not found")
    return encounter


def _lock_patient_then_encounter(db: Session, encounter_id: int) -> tuple[Patient, Encounter]:
    """Lock in the global Patient -> Encounter order used by intake and actions."""
    patient_id = db.execute(
        select(Encounter.patient_id).where(Encounter.encounter_id == encounter_id)
    ).scalar_one_or_none()
    if patient_id is None:
        raise LifecycleNotFound("Encounter not found")
    patient = db.execute(
        select(Patient)
        .where(Patient.patient_id == patient_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if patient is None:
        raise LifecycleNotFound("Patient not found")
    encounter = _lock_encounter(db, encounter_id)
    return patient, encounter


def _lock_beds(db: Session, bed_ids: Iterable[str]) -> dict[str, Bed]:
    ids = sorted(set(bed_ids))
    if not ids:
        return {}
    beds = db.execute(
        select(Bed).where(Bed.bed_id.in_(ids)).order_by(Bed.bed_id).with_for_update()
    ).scalars().all()
    found = {bed.bed_id: bed for bed in beds}
    missing = next((bed_id for bed_id in ids if bed_id not in found), None)
    if missing is not None:
        raise LifecycleNotFound(f"Bed {missing} not found")
    return found


def _lock_equipment(db: Session, equipment_ids: Iterable[str]) -> dict[str, Equipment]:
    ids = sorted(set(equipment_ids))
    if not ids:
        return {}
    equipment = db.execute(
        select(Equipment)
        .where(Equipment.equipment_id.in_(ids))
        .order_by(Equipment.equipment_id)
        .with_for_update()
    ).scalars().all()
    found = {item.equipment_id: item for item in equipment}
    missing = next((equipment_id for equipment_id in ids if equipment_id not in found), None)
    if missing is not None:
        raise LifecycleNotFound(f"Equipment {missing} not found")
    return found


def _active_bed_assignment(db: Session, encounter_id: int) -> BedAssignment | None:
    return db.execute(
        select(BedAssignment)
        .where(BedAssignment.encounter_id == encounter_id, BedAssignment.released_at.is_(None))
    ).scalar_one_or_none()


def _active_equipment_assignments(db: Session, encounter_id: int) -> list[EquipmentAssignment]:
    return db.execute(
        select(EquipmentAssignment)
        .where(
            EquipmentAssignment.encounter_id == encounter_id,
            EquipmentAssignment.released_at.is_(None),
        )
        .order_by(EquipmentAssignment.equipment_id)
    ).scalars().all()


def _validate_bed(encounter: Encounter, bed: Bed) -> None:
    if bed.status.upper() != "AVAILABLE":
        raise LifecycleConflict("Bed is not available")
    try:
        allowed_types = candidate_bed_types(encounter.acuity)
    except ValueError as exc:
        raise LifecycleValidationError("Invalid encounter acuity") from exc
    if bed.bed_type not in allowed_types:
        raise LifecycleValidationError("Bed type is incompatible with patient acuity")
    if encounter.isolation_required and not bed.isolation_capable:
        raise LifecycleValidationError("Patient requires an isolation-capable bed")


def _flush(db: Session) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        # Translate only the three active-assignment partial unique indexes.
        # All other integrity failures (including foreign keys) keep their
        # original type and details. In either case, the caller rolls back.
        known_indexes = {
            "uq_bed_assignments_active_bed",
            "uq_bed_assignments_active_encounter",
            "uq_equipment_assignments_active_equipment",
        }
        constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        sqlite_unique_columns = {
            "UNIQUE constraint failed: bed_assignments.bed_id",
            "UNIQUE constraint failed: bed_assignments.encounter_id",
            "UNIQUE constraint failed: equipment_assignments.equipment_id",
        }
        is_active_assignment_conflict = (
            constraint_name in known_indexes
            or str(exc.orig) in sqlite_unique_columns
        )
        if is_active_assignment_conflict:
            raise LifecycleConflict("A resource already has an active assignment") from exc
        raise


def create_encounter(
    db: Session,
    patient_id: str,
    *,
    acuity: int | None = None,
    specialty: str | None = None,
    predicted_los: float | None = None,
    isolation_required: bool | None = None,
    ventilator_required: bool | None = None,
    arrival_time: datetime | None = None,
) -> Encounter:
    """Create a WAITING admission using optional clinical-field overrides.

    When overrides are omitted, current Patient admission fields are copied for
    compatibility with the existing intake data model. Patient-level locking
    serializes concurrent encounter creation for the same identity.
    """
    patient = db.execute(
        select(Patient).where(Patient.patient_id == patient_id).with_for_update()
    ).scalar_one_or_none()
    if patient is None:
        raise LifecycleNotFound("Patient not found")

    active = db.execute(
        select(Encounter).where(
            Encounter.patient_id == patient_id,
            Encounter.status.in_(("WAITING", "ADMITTED")),
        ).with_for_update()
    ).scalar_one_or_none()
    if active is not None or patient.current_status.upper() == "ADMITTED":
        raise LifecycleConflict("Patient already has an active admission")

    encounter_acuity = patient.acuity if acuity is None else acuity
    try:
        candidate_bed_types(encounter_acuity)
    except ValueError as exc:
        raise LifecycleValidationError("Invalid encounter acuity") from exc

    encounter = Encounter(
        patient_id=patient.patient_id,
        acuity=encounter_acuity,
        specialty=patient.specialty if specialty is None else specialty,
        predicted_los=patient.predicted_los if predicted_los is None else predicted_los,
        isolation_required=(patient.isolation_required if isolation_required is None else isolation_required),
        ventilator_required=(patient.ventilator_required if ventilator_required is None else ventilator_required),
        arrival_time=patient.arrival_time if arrival_time is None else arrival_time,
        status="WAITING",
    )
    patient.current_status = "WAITING"
    db.add(encounter)
    _record(db, encounter, "ENCOUNTER_CREATED")
    _flush(db)
    return encounter


def approve_encounter(
    db: Session,
    encounter_id: int,
    bed_id: str,
    *,
    actor_id: int | object | None = None,
    equipment_id: str | None = None,
    algorithm: str = "lifecycle",
) -> Encounter:
    """Admit a waiting Encounter and atomically assign its bed/equipment."""
    patient, encounter = _lock_patient_then_encounter(db, encounter_id)
    if patient.current_status.upper() != "WAITING":
        raise LifecycleConflict("Patient is not waiting for admission")
    if encounter.status.upper() != "WAITING":
        raise LifecycleConflict("Encounter is not waiting for allocation")
    actor = _actor_id(actor_id)

    bed = _lock_beds(db, [bed_id])[bed_id]
    _validate_bed(encounter, bed)

    selected_equipment_id = equipment_id
    if encounter.ventilator_required and selected_equipment_id is None:
        candidate = db.execute(
            select(Equipment.equipment_id)
            .where(Equipment.type == "VENTILATOR", Equipment.status == "AVAILABLE")
            .order_by(Equipment.equipment_id)
            .limit(1)
        ).scalar_one_or_none()
        if candidate is None:
            raise LifecycleConflict("No available ventilator")
        selected_equipment_id = candidate
    if encounter.ventilator_required and selected_equipment_id is None:
        raise LifecycleConflict("No available ventilator")

    equipment_by_id = _lock_equipment(db, [selected_equipment_id] if selected_equipment_id else [])
    selected_equipment = equipment_by_id.get(selected_equipment_id) if selected_equipment_id else None
    if encounter.ventilator_required:
        assert selected_equipment is not None
        if selected_equipment.type.upper() != "VENTILATOR":
            raise LifecycleValidationError("Required equipment must be a ventilator")
        if selected_equipment.status.upper() != "AVAILABLE":
            raise LifecycleConflict("Equipment is not available")
    elif selected_equipment_id is not None:
        raise LifecycleValidationError("Equipment cannot be assigned when the Encounter does not require a ventilator")

    now = _now()
    bed.status = "OCCUPIED"
    db.add(BedAssignment(
        encounter_id=encounter.encounter_id,
        bed_id=bed.bed_id,
        assigned_at=now,
        assigned_by=actor,
    ))
    if selected_equipment is not None:
        selected_equipment.status = "IN_USE"
        db.add(EquipmentAssignment(
            encounter_id=encounter.encounter_id,
            equipment_id=selected_equipment.equipment_id,
            assigned_at=now,
            assigned_by=actor,
        ))
    encounter.status = "ADMITTED"
    encounter.admitted_at = now
    patient.current_status = "ADMITTED"
    _record(db, encounter, "ADMITTED", bed.bed_id, algorithm=algorithm)
    _flush(db)
    return encounter


def discharge_encounter(
    db: Session,
    encounter_id: int,
    *,
    actor_id: int | object | None = None,
    release_reason: str = "discharge",
) -> Encounter:
    """Discharge and release assignment-tracked resources; bed enters CLEANING."""
    patient, encounter = _lock_patient_then_encounter(db, encounter_id)
    if encounter.status.upper() != "ADMITTED":
        raise LifecycleConflict("Only an admitted Encounter can be discharged")
    actor = _actor_id(actor_id)
    bed_assignment = _active_bed_assignment(db, encounter_id)
    equipment_assignments = _active_equipment_assignments(db, encounter_id)
    if bed_assignment is None:
        raise LifecycleConflict("Admitted Encounter has no active bed assignment")

    beds = _lock_beds(db, [bed_assignment.bed_id])
    bed = beds[bed_assignment.bed_id]
    if bed.status.upper() != "OCCUPIED":
        raise LifecycleConflict("Active bed assignment points to a bed that is not occupied")
    equipment = _lock_equipment(db, [item.equipment_id for item in equipment_assignments])
    for assignment in equipment_assignments:
        item = equipment[assignment.equipment_id]
        if item.status.upper() != "IN_USE":
            raise LifecycleConflict(f"Assigned equipment {item.equipment_id} is not in use")

    now = _now()
    bed_assignment.released_at = now
    bed_assignment.release_reason = release_reason
    bed.status = "CLEANING"
    for assignment in equipment_assignments:
        assignment.released_at = now
        assignment.release_reason = release_reason
        equipment[assignment.equipment_id].status = "AVAILABLE"
    encounter.status = "DISCHARGED"
    encounter.discharged_at = now
    # Discharged patients leave the waiting queue; only a new admission
    # (create_encounter) can place the patient back in WAITING.
    patient.current_status = "DISCHARGED"
    _record(db, encounter, "DISCHARGED", bed.bed_id)
    _flush(db)
    return encounter


def complete_bed_cleaning(db: Session, bed_id: str) -> Bed:
    """Mark cleaning complete.

    No AuditLog row is written because that schema requires a patient_id for
    every event. Bed-scoped audit events need a future nullable patient_id or a
    separate bed-event record; this service does not invent patient ownership.
    """
    bed = _lock_beds(db, [bed_id])[bed_id]
    if bed.status.upper() != "CLEANING":
        raise LifecycleConflict("Bed is not in cleaning status")
    active = db.execute(
        select(BedAssignment.assignment_id)
        .where(BedAssignment.bed_id == bed_id, BedAssignment.released_at.is_(None))
        .with_for_update()
    ).scalar_one_or_none()
    if active is not None:
        raise LifecycleConflict("Bed still has an active assignment")
    bed.status = "AVAILABLE"
    _flush(db)
    return bed


def transfer_encounter(
    db: Session,
    encounter_id: int,
    destination_bed_id: str,
    *,
    actor_id: int | object | None = None,
    release_reason: str = "transfer",
) -> Encounter:
    """Transfer an admitted Encounter, preserving both bed assignment rows."""
    _, encounter = _lock_patient_then_encounter(db, encounter_id)
    if encounter.status.upper() != "ADMITTED":
        raise LifecycleConflict("Only an admitted Encounter can be transferred")
    actor = _actor_id(actor_id)
    previous = _active_bed_assignment(db, encounter_id)
    if previous is None:
        raise LifecycleConflict("Admitted Encounter has no active bed assignment")
    beds = _lock_beds(db, [previous.bed_id, destination_bed_id])
    old_bed = beds[previous.bed_id]
    destination = beds[destination_bed_id]
    if destination_bed_id == previous.bed_id:
        raise LifecycleConflict("Destination bed is already assigned to this Encounter")
    _validate_bed(encounter, destination)
    if old_bed.status.upper() != "OCCUPIED":
        raise LifecycleConflict("Current assigned bed is not occupied")

    now = _now()
    previous.released_at = now
    previous.release_reason = release_reason
    old_bed.status = "CLEANING"
    destination.status = "OCCUPIED"
    db.add(BedAssignment(
        encounter_id=encounter.encounter_id,
        bed_id=destination.bed_id,
        assigned_at=now,
        assigned_by=actor,
    ))
    _record(db, encounter, "TRANSFERRED", destination.bed_id)
    _flush(db)
    return encounter


def assign_equipment(
    db: Session,
    encounter_id: int,
    equipment_id: str,
    *,
    actor_id: int | object | None = None,
) -> EquipmentAssignment:
    """Assign one available equipment item to an admitted Encounter."""
    _, encounter = _lock_patient_then_encounter(db, encounter_id)
    if encounter.status.upper() != "ADMITTED":
        raise LifecycleConflict("Equipment can only be assigned to an admitted Encounter")
    actor = _actor_id(actor_id)
    item = _lock_equipment(db, [equipment_id])[equipment_id]
    if item.status.upper() != "AVAILABLE":
        raise LifecycleConflict("Equipment is not available")
    existing = db.execute(
        select(EquipmentAssignment.assignment_id).where(
            EquipmentAssignment.encounter_id == encounter_id,
            EquipmentAssignment.equipment_id == equipment_id,
            EquipmentAssignment.released_at.is_(None),
        ).with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        raise LifecycleConflict("Equipment is already assigned to this Encounter")
    assignment = EquipmentAssignment(
        encounter_id=encounter_id,
        equipment_id=equipment_id,
        assigned_at=_now(),
        assigned_by=actor,
    )
    item.status = "IN_USE"
    db.add(assignment)
    _record(db, encounter, "EQUIPMENT_ASSIGNED")
    _flush(db)
    return assignment


def release_equipment(
    db: Session,
    encounter_id: int,
    equipment_id: str,
    *,
    release_reason: str = "released",
) -> EquipmentAssignment:
    """Release only an item with a matching active assignment record."""
    _, encounter = _lock_patient_then_encounter(db, encounter_id)
    if encounter.status.upper() != "ADMITTED":
        raise LifecycleConflict("Equipment can only be released from an admitted Encounter")
    assignment = db.execute(
        select(EquipmentAssignment).where(
            EquipmentAssignment.encounter_id == encounter_id,
            EquipmentAssignment.equipment_id == equipment_id,
            EquipmentAssignment.released_at.is_(None),
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise LifecycleConflict("No active equipment assignment exists for this Encounter")
    item = _lock_equipment(db, [equipment_id])[equipment_id]
    if item.status.upper() != "IN_USE":
        raise LifecycleConflict("Assigned equipment is not in use")
    assignment.released_at = _now()
    assignment.release_reason = release_reason
    item.status = "AVAILABLE"
    _record(db, encounter, "EQUIPMENT_RELEASED")
    _flush(db)
    return assignment


def get_active_assignments(
    db: Session, encounter_id: int
) -> tuple[BedAssignment | None, list[EquipmentAssignment]]:
    """Return the Encounter's active bed assignment and active equipment rows."""
    if db.get(Encounter, encounter_id) is None:
        raise LifecycleNotFound("Encounter not found")
    return (
        db.execute(
            select(BedAssignment).where(
                BedAssignment.encounter_id == encounter_id,
                BedAssignment.released_at.is_(None),
            )
        ).scalar_one_or_none(),
        db.execute(
            select(EquipmentAssignment)
            .where(
                EquipmentAssignment.encounter_id == encounter_id,
                EquipmentAssignment.released_at.is_(None),
            )
            .order_by(EquipmentAssignment.equipment_id)
        ).scalars().all(),
    )
