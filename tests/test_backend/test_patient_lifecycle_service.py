"""Service-level coverage for Encounter and resource lifecycle transitions."""
from datetime import datetime, timezone

import pytest

from backend.models import (
    Bed,
    BedAssignment,
    Encounter,
    Equipment,
    EquipmentAssignment,
    Patient,
    User,
)
from backend.services import patient_lifecycle as lifecycle
from backend.services.patient_lifecycle import (
    LifecycleConflict,
    LifecycleNotFound,
    LifecycleValidationError,
)


def _patient(db_session, *, acuity=3, isolation=False, ventilator=False, status="WAITING"):
    patient_id = f"L{db_session.query(Patient).count() + 1:05d}"
    patient = Patient(
        patient_id=patient_id,
        age_group="adult",
        acuity=acuity,
        specialty="General",
        predicted_los=2.0,
        isolation_required=isolation,
        ventilator_required=ventilator,
        arrival_time=datetime.now(timezone.utc),
        current_status=status,
    )
    db_session.add(patient)
    db_session.commit()
    return patient


def _user(db_session):
    user = User(
        username="lifecycle_user",
        email="lifecycle@example.com",
        hashed_password="test",
        role="doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _encounter(db_session, **patient_kwargs):
    patient = _patient(db_session, **patient_kwargs)
    return lifecycle.create_encounter(db_session, patient.patient_id)


def _compatible_bed(db_session, encounter, *, status="AVAILABLE", isolation=None):
    bed_type = lifecycle.candidate_bed_types(encounter.acuity)[-1]
    bed = Bed(
        bed_id="LIFEBED1",
        bed_type=bed_type,
        ward="Lifecycle",
        status=status,
        isolation_capable=encounter.isolation_required if isolation is None else isolation,
    )
    db_session.add(bed)
    db_session.commit()
    return bed


def _equipment(db_session, *, equipment_id="LIFEEQ01", status="AVAILABLE", item_type="VENTILATOR"):
    item = Equipment(
        equipment_id=equipment_id,
        type=item_type,
        status=status,
        location="Lifecycle",
    )
    db_session.add(item)
    db_session.commit()
    return item


def test_successful_admission_creates_encounter_assignments_and_actor_history(db_session):
    user = _user(db_session)
    encounter = _encounter(db_session, ventilator=True)
    patient = db_session.get(Patient, encounter.patient_id)
    bed = _compatible_bed(db_session, encounter)
    ventilator = _equipment(db_session)

    lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id,
                                actor_id=user.id, equipment_id=ventilator.equipment_id)
    db_session.commit()
    db_session.refresh(encounter)
    db_session.refresh(bed)
    db_session.refresh(ventilator)

    bed_assignment, equipment_assignments = lifecycle.get_active_assignments(db_session, encounter.encounter_id)
    assert encounter.status == "ADMITTED"
    assert encounter.admitted_at is not None
    assert patient.current_status == "ADMITTED"
    assert bed.status == "OCCUPIED"
    assert ventilator.status == "IN_USE"
    assert bed_assignment.bed_id == bed.bed_id
    assert bed_assignment.assigned_by == user.id
    assert len(equipment_assignments) == 1
    assert equipment_assignments[0].equipment_id == ventilator.equipment_id
    assert equipment_assignments[0].assigned_by == user.id


def test_admission_rejects_patient_not_waiting_under_lock(db_session):
    encounter = _encounter(db_session)
    patient = db_session.get(Patient, encounter.patient_id)
    bed = _compatible_bed(db_session, encounter)
    patient.current_status = "ADMITTED"
    db_session.commit()

    with pytest.raises(LifecycleConflict, match="Patient is not waiting"):
        lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id)
    db_session.rollback()

    db_session.refresh(patient)
    db_session.refresh(encounter)
    db_session.refresh(bed)
    assert patient.current_status == "ADMITTED"
    assert encounter.status == "WAITING"
    assert bed.status == "AVAILABLE"
    assert db_session.query(BedAssignment).filter(
        BedAssignment.encounter_id == encounter.encounter_id
    ).count() == 0


@pytest.mark.parametrize("failure", ["unavailable", "wrong_tier", "isolation"])
def test_admission_validation_failure_leaves_no_partial_writes(db_session, failure):
    encounter = _encounter(db_session, acuity=5 if failure == "wrong_tier" else 3,
                            isolation=failure == "isolation", ventilator=True)
    if failure == "wrong_tier":
        bed = Bed(bed_id="LIFEBED1", bed_type="WARD", ward="Lifecycle", status="AVAILABLE", isolation_capable=True)
        db_session.add(bed)
    else:
        bed = _compatible_bed(db_session, encounter, status="OCCUPIED" if failure == "unavailable" else "AVAILABLE",
                              isolation=False if failure == "isolation" else None)
    _equipment(db_session)
    db_session.commit()

    expected = LifecycleConflict if failure == "unavailable" else LifecycleValidationError
    with pytest.raises(expected):
        lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id)
    db_session.rollback()
    db_session.refresh(encounter)
    db_session.refresh(bed)
    equipment = db_session.query(Equipment).filter_by(equipment_id="LIFEEQ01").one()
    assert encounter.status == "WAITING"
    assert bed.status == ("OCCUPIED" if failure == "unavailable" else "AVAILABLE")
    assert equipment.status == "AVAILABLE"
    assert db_session.query(BedAssignment).count() == 0
    assert db_session.query(EquipmentAssignment).count() == 0


def test_missing_patient_and_conflicting_active_encounter_are_rejected(db_session):
    with pytest.raises(LifecycleNotFound):
        lifecycle.create_encounter(db_session, "MISSING")
    patient = _patient(db_session)
    lifecycle.create_encounter(db_session, patient.patient_id)
    db_session.commit()
    with pytest.raises(LifecycleConflict, match="active admission"):
        lifecycle.create_encounter(db_session, patient.patient_id)


def test_duplicate_active_bed_and_equipment_assignments_are_rejected(db_session):
    encounter = _encounter(db_session, ventilator=True)
    bed = _compatible_bed(db_session, encounter)
    equipment = _equipment(db_session)
    lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id,
                                equipment_id=equipment.equipment_id)
    db_session.commit()
    with pytest.raises(LifecycleConflict):
        lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id)
    with pytest.raises(LifecycleConflict):
        lifecycle.assign_equipment(db_session, encounter.encounter_id, equipment.equipment_id)

    other = _encounter(db_session, ventilator=False)
    with pytest.raises(LifecycleConflict):
        lifecycle.approve_encounter(db_session, other.encounter_id, bed.bed_id)
    db_session.rollback()
    assert db_session.query(BedAssignment).filter_by(released_at=None).count() == 1
    assert db_session.query(EquipmentAssignment).filter_by(released_at=None).count() == 1


def test_discharge_releases_all_equipment_and_puts_bed_into_cleaning(db_session):
    encounter = _encounter(db_session, ventilator=True)
    patient = db_session.get(Patient, encounter.patient_id)
    bed = _compatible_bed(db_session, encounter)
    ventilator = _equipment(db_session)
    other_equipment = _equipment(db_session, equipment_id="LIFEEQ02", item_type="MONITOR")
    lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id,
                                equipment_id=ventilator.equipment_id)
    lifecycle.assign_equipment(db_session, encounter.encounter_id, other_equipment.equipment_id)
    db_session.commit()

    lifecycle.discharge_encounter(db_session, encounter.encounter_id, release_reason="clinical discharge")
    db_session.commit()
    db_session.refresh(encounter)
    db_session.refresh(bed)
    db_session.refresh(ventilator)
    db_session.refresh(other_equipment)

    assert encounter.status == "DISCHARGED"
    assert encounter.discharged_at is not None
    assert patient.current_status == "DISCHARGED"
    assert bed.status == "CLEANING"
    assert ventilator.status == other_equipment.status == "AVAILABLE"
    assert db_session.query(BedAssignment).filter_by(encounter_id=encounter.encounter_id, released_at=None).count() == 0
    assert db_session.query(EquipmentAssignment).filter_by(encounter_id=encounter.encounter_id, released_at=None).count() == 0
    assert db_session.query(BedAssignment).filter_by(encounter_id=encounter.encounter_id).count() == 1
    assert db_session.query(EquipmentAssignment).filter_by(encounter_id=encounter.encounter_id).count() == 2


@pytest.mark.parametrize("status", ["WAITING", "DISCHARGED"])
def test_discharge_rejects_non_admitted_encounter(db_session, status):
    encounter = _encounter(db_session)
    encounter.status = status
    db_session.commit()
    with pytest.raises(LifecycleConflict):
        lifecycle.discharge_encounter(db_session, encounter.encounter_id)


def test_cleaning_completion_requires_cleaning_and_no_active_assignment(db_session):
    encounter = _encounter(db_session)
    bed = _compatible_bed(db_session, encounter, status="CLEANING")
    lifecycle.complete_bed_cleaning(db_session, bed.bed_id)
    db_session.commit()
    assert db_session.get(Bed, bed.bed_id).status == "AVAILABLE"
    assert db_session.query(lifecycle.AuditLog).filter_by(
        action="BED_CLEANING_COMPLETED", bed_id=bed.bed_id
    ).count() == 0


def test_flush_translates_known_active_assignment_unique_violation(db_session):
    encounter = _encounter(db_session)
    bed = _compatible_bed(db_session, encounter)
    lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id)
    db_session.commit()
    db_session.add(BedAssignment(
        encounter_id=encounter.encounter_id,
        bed_id=bed.bed_id,
        assigned_at=datetime.now(timezone.utc),
    ))

    with pytest.raises(LifecycleConflict, match="active assignment"):
        lifecycle._flush(db_session)
    db_session.rollback()


def test_flush_reraises_unrelated_integrity_error(db_session, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    error = IntegrityError("INSERT", {}, Exception("FOREIGN KEY constraint failed"))
    monkeypatch.setattr(db_session, "flush", lambda: (_ for _ in ()).throw(error))

    with pytest.raises(IntegrityError) as raised:
        lifecycle._flush(db_session)
    assert raised.value is error


def test_readmission_creates_separate_encounter_and_preserves_resource_history(db_session):
    patient = _patient(db_session, ventilator=True)
    first = lifecycle.create_encounter(db_session, patient.patient_id)
    bed = _compatible_bed(db_session, first)
    ventilator = _equipment(db_session)
    lifecycle.approve_encounter(
        db_session, first.encounter_id, bed.bed_id, equipment_id=ventilator.equipment_id
    )
    db_session.commit()

    lifecycle.discharge_encounter(db_session, first.encounter_id)
    db_session.commit()
    db_session.refresh(patient)
    assert patient.current_status == "DISCHARGED"
    lifecycle.complete_bed_cleaning(db_session, bed.bed_id)
    db_session.commit()

    second = lifecycle.create_encounter(db_session, patient.patient_id)
    db_session.refresh(patient)
    assert patient.current_status == "WAITING"
    lifecycle.approve_encounter(
        db_session, second.encounter_id, bed.bed_id, equipment_id=ventilator.equipment_id
    )
    db_session.commit()

    db_session.refresh(first)
    db_session.refresh(second)
    db_session.refresh(patient)
    assert first.status == "DISCHARGED"
    assert second.status == "ADMITTED"
    assert patient.current_status == "ADMITTED"
    first_bed_history = db_session.query(BedAssignment).filter_by(encounter_id=first.encounter_id).all()
    second_bed_history = db_session.query(BedAssignment).filter_by(encounter_id=second.encounter_id).all()
    first_equipment_history = db_session.query(EquipmentAssignment).filter_by(encounter_id=first.encounter_id).all()
    second_equipment_history = db_session.query(EquipmentAssignment).filter_by(encounter_id=second.encounter_id).all()
    assert len(first_bed_history) == len(second_bed_history) == 1
    assert first_bed_history[0].bed_id == second_bed_history[0].bed_id == bed.bed_id
    assert first_bed_history[0].released_at is not None
    assert second_bed_history[0].released_at is None
    assert len(first_equipment_history) == len(second_equipment_history) == 1
    assert first_equipment_history[0].equipment_id == second_equipment_history[0].equipment_id == ventilator.equipment_id
    assert first_equipment_history[0].released_at is not None
    assert second_equipment_history[0].released_at is None


def test_discharge_rejects_assigned_bed_not_occupied_without_partial_changes(db_session):
    encounter = _encounter(db_session, ventilator=True)
    patient = db_session.get(Patient, encounter.patient_id)
    bed = _compatible_bed(db_session, encounter)
    ventilator = _equipment(db_session)
    lifecycle.approve_encounter(
        db_session, encounter.encounter_id, bed.bed_id, equipment_id=ventilator.equipment_id
    )
    db_session.commit()
    bed.status = "AVAILABLE"
    db_session.commit()

    with pytest.raises(LifecycleConflict, match="not occupied"):
        lifecycle.discharge_encounter(db_session, encounter.encounter_id)
    db_session.rollback()
    db_session.expire_all()

    bed_assignment, equipment_assignments = lifecycle.get_active_assignments(db_session, encounter.encounter_id)
    assert db_session.get(Encounter, encounter.encounter_id).status == "ADMITTED"
    assert db_session.get(Patient, patient.patient_id).current_status == "ADMITTED"
    assert db_session.get(Bed, bed.bed_id).status == "AVAILABLE"
    assert db_session.get(Equipment, ventilator.equipment_id).status == "IN_USE"
    assert bed_assignment.released_at is None
    assert len(equipment_assignments) == 1 and equipment_assignments[0].released_at is None


def test_cleaning_completion_rejects_bed_with_active_assignment(db_session):
    encounter = _encounter(db_session)
    bed = _compatible_bed(db_session, encounter)
    lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id)
    db_session.commit()
    bed.status = "CLEANING"
    db_session.commit()
    with pytest.raises(LifecycleConflict, match="active assignment"):
        lifecycle.complete_bed_cleaning(db_session, bed.bed_id)


def test_transfer_releases_old_assignment_and_preserves_history(db_session):
    encounter = _encounter(db_session)
    old_bed = _compatible_bed(db_session, encounter)
    new_bed = Bed(
        bed_id="LIFEBED2",
        bed_type=old_bed.bed_type,
        ward="Lifecycle-2",
        status="AVAILABLE",
        isolation_capable=old_bed.isolation_capable,
    )
    db_session.add(new_bed)
    lifecycle.approve_encounter(db_session, encounter.encounter_id, old_bed.bed_id)
    db_session.commit()

    lifecycle.transfer_encounter(db_session, encounter.encounter_id, new_bed.bed_id)
    db_session.commit()
    db_session.refresh(old_bed)
    db_session.refresh(new_bed)
    history = db_session.query(BedAssignment).filter_by(encounter_id=encounter.encounter_id).order_by(BedAssignment.assignment_id).all()
    assert old_bed.status == "CLEANING"
    assert new_bed.status == "OCCUPIED"
    assert len(history) == 2
    assert history[0].bed_id == old_bed.bed_id and history[0].released_at is not None
    assert history[1].bed_id == new_bed.bed_id and history[1].released_at is None


def test_equipment_assignment_and_release_preserve_history(db_session):
    encounter = _encounter(db_session)
    bed = _compatible_bed(db_session, encounter)
    equipment = _equipment(db_session, item_type="MONITOR")
    lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id)
    db_session.commit()
    assignment = lifecycle.assign_equipment(db_session, encounter.encounter_id, equipment.equipment_id)
    db_session.commit()
    assert db_session.get(Equipment, equipment.equipment_id).status == "IN_USE"
    lifecycle.release_equipment(db_session, encounter.encounter_id, equipment.equipment_id, release_reason="no longer needed")
    db_session.commit()
    db_session.refresh(assignment)
    assert assignment.released_at is not None
    assert assignment.release_reason == "no longer needed"
    assert db_session.get(Equipment, equipment.equipment_id).status == "AVAILABLE"
    with pytest.raises(LifecycleConflict):
        lifecycle.release_equipment(db_session, encounter.encounter_id, equipment.equipment_id)


def test_equipment_assignment_rejects_unavailable_item(db_session):
    encounter = _encounter(db_session)
    bed = _compatible_bed(db_session, encounter)
    item = _equipment(db_session, status="IN_USE", item_type="MONITOR")
    lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id)
    db_session.commit()

    with pytest.raises(LifecycleConflict, match="not available"):
        lifecycle.assign_equipment(db_session, encounter.encounter_id, item.equipment_id)
    db_session.rollback()
    assert db_session.get(Equipment, item.equipment_id).status == "IN_USE"
    assert db_session.query(EquipmentAssignment).filter_by(equipment_id=item.equipment_id).count() == 0


def test_assignment_failure_rolls_back_as_one_caller_owned_transaction(db_session, monkeypatch):
    encounter = _encounter(db_session, ventilator=True)
    bed = _compatible_bed(db_session, encounter)
    ventilator = _equipment(db_session)
    real_flush = lifecycle._flush

    def fail_after_flush(session):
        real_flush(session)
        raise RuntimeError("injected post-flush failure")

    monkeypatch.setattr(lifecycle, "_flush", fail_after_flush)
    with pytest.raises(RuntimeError, match="injected"):
        lifecycle.approve_encounter(db_session, encounter.encounter_id, bed.bed_id,
                                    equipment_id=ventilator.equipment_id)
    db_session.rollback()
    db_session.expire_all()
    assert db_session.get(Encounter, encounter.encounter_id).status == "WAITING"
    assert db_session.get(Bed, bed.bed_id).status == "AVAILABLE"
    assert db_session.get(Equipment, ventilator.equipment_id).status == "AVAILABLE"
    assert db_session.query(BedAssignment).count() == 0
    assert db_session.query(EquipmentAssignment).count() == 0


def test_legacy_occupied_and_in_use_resources_are_never_inferred_or_released(db_session):
    encounter = _encounter(db_session, ventilator=False)
    legacy_bed = _compatible_bed(db_session, encounter, status="OCCUPIED")
    legacy_equipment = _equipment(db_session, status="IN_USE")

    active_encounter = _encounter(db_session)
    assigned_bed = Bed(
        bed_id="LIFEBED2",
        bed_type=legacy_bed.bed_type,
        ward="Lifecycle-2",
        status="AVAILABLE",
        isolation_capable=True,
    )
    db_session.add(assigned_bed)
    db_session.commit()
    lifecycle.approve_encounter(db_session, active_encounter.encounter_id, assigned_bed.bed_id)
    db_session.commit()
    lifecycle.discharge_encounter(db_session, active_encounter.encounter_id)
    db_session.commit()

    assert db_session.get(Bed, legacy_bed.bed_id).status == "OCCUPIED"
    assert db_session.get(Equipment, legacy_equipment.equipment_id).status == "IN_USE"
    assert db_session.query(BedAssignment).filter_by(bed_id=legacy_bed.bed_id).count() == 0
    assert db_session.query(EquipmentAssignment).filter_by(equipment_id=legacy_equipment.equipment_id).count() == 0


def test_legacy_occupied_bed_cannot_be_transferred_without_assignment_history(db_session):
    encounter = _encounter(db_session)
    legacy_bed = _compatible_bed(db_session, encounter, status="OCCUPIED")
    encounter.status = "ADMITTED"
    db_session.commit()
    destination = Bed(
        bed_id="LIFEBED2",
        bed_type=legacy_bed.bed_type,
        ward="Lifecycle-2",
        status="AVAILABLE",
        isolation_capable=True,
    )
    db_session.add(destination)
    db_session.commit()

    with pytest.raises(LifecycleConflict, match="no active bed assignment"):
        lifecycle.transfer_encounter(db_session, encounter.encounter_id, destination.bed_id)
    db_session.rollback()
    assert db_session.get(Bed, legacy_bed.bed_id).status == "OCCUPIED"
    assert db_session.get(Bed, destination.bed_id).status == "AVAILABLE"
    assert db_session.query(BedAssignment).count() == 0
