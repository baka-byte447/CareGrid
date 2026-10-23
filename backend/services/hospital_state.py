"""
Bridges the PostgreSQL rows to the simulator's in-memory types, so the API asks
the SAME allocation code the simulator uses (simulator/hospital/policy.py)
instead of keeping its own copy of the rules.
"""
from sqlalchemy.orm import Session

from backend.models import Bed, Equipment
from backend.models import Patient as PatientRow
from simulator.hospital.state import Bed as SimBed
from simulator.hospital.state import Equipment as SimEquipment
from simulator.hospital.state import HospitalState
from simulator.patients.patient import Patient as SimPatient


def build_hospital_state(db: Session) -> HospitalState:
    """Snapshot of the current beds and equipment (statuses as stored in the DB)."""
    state = HospitalState()
    for b in db.query(Bed).all():
        state.beds[b.bed_id] = SimBed(
            bed_id=b.bed_id, bed_type=b.bed_type, ward=b.ward,
            status=b.status.upper(), isolation_capable=b.isolation_capable)
    for e in db.query(Equipment).all():
        state.equipment[e.equipment_id] = SimEquipment(
            equipment_id=e.equipment_id, type=e.type,
            status=e.status.upper(), location=e.location)
    return state


def to_simulator_patient(row: PatientRow) -> SimPatient:
    return SimPatient(
        patient_id=row.patient_id, age_group=row.age_group, acuity=row.acuity,
        specialty=row.specialty, predicted_los=row.predicted_los,
        isolation_required=row.isolation_required,
        ventilator_required=row.ventilator_required,
        arrival_time=row.arrival_time,
    )
