"""
Bridges the PostgreSQL rows to the simulator's in-memory types, so the API asks
the SAME allocation code the simulator uses (simulator/hospital/policy.py)
instead of keeping its own copy of the rules.

Simulated-time model
--------------------
All patient data in the database uses *simulated* timestamps (e.g. Oct–Dec 2026),
not wall-clock time.  ``build_hospital_state`` therefore derives ``state.current_time``
from the **latest patient arrival_time** found in the database — this is the furthest
point along the simulated timeline and is used by:

* G2 max-wait guardrails  (safety/layer.py ``_patient_wait_hours``)
* RL observation v2       (rl/environment/observation.py ``wait_so_far`` feature)

Wall-clock UTC is used only as a fallback when the database is empty.
"""
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import Bed, BedAssignment, Encounter, Equipment
from backend.models import Patient as PatientRow
from simulator.hospital.state import Bed as SimBed
from simulator.hospital.state import Equipment as SimEquipment
from simulator.hospital.state import HospitalState
from simulator.patients.patient import Patient as SimPatient


def build_hospital_state(db: Session) -> HospitalState:
    """Snapshot of current beds, equipment, waiting queue, admitted patients, and time.

    Simulated clock
    ~~~~~~~~~~~~~~~
    ``state.current_time`` is set to the **maximum patient arrival_time** in the
    database so that all wait-time computations operate on the simulated timeline
    rather than wall-clock UTC.  When the DB is empty, falls back to UTC now.

    Queue membership
    ~~~~~~~~~~~~~~~~
    Patients with ``current_status == "WAITING"`` are authoritative for the queue.
    ``patients.current_status`` is kept in sync by ``patient_lifecycle.py``; it
    is denormalized from (and must agree with) the corresponding ``Encounter.status``.

    Admitted-patient map
    ~~~~~~~~~~~~~~~~~~~~
    ``state.admitted_patients`` is populated from active ``BedAssignment`` rows
    (those without a ``released_at``).  Legacy OCCUPIED beds without a matching
    BedAssignment are intentionally excluded (see migration c41a7d9e2b60).
    """
    state = HospitalState()

    # --- Beds ---
    for b in db.query(Bed).all():
        state.beds[b.bed_id] = SimBed(
            bed_id=b.bed_id, bed_type=b.bed_type, ward=b.ward,
            status=b.status.upper(), isolation_capable=b.isolation_capable,
        )

    # --- Equipment ---
    for e in db.query(Equipment).all():
        state.equipment[e.equipment_id] = SimEquipment(
            equipment_id=e.equipment_id, type=e.type,
            status=e.status.upper(), location=e.location,
        )

    # --- Waiting queue (ordered by arrival time — longest wait first) ---
    waiting_patients = (
        db.query(PatientRow)
        .filter(PatientRow.current_status == "WAITING")
        .order_by(PatientRow.arrival_time)
        .all()
    )
    state.waiting_queue = [p.patient_id for p in waiting_patients]

    # --- Admitted-patient map (patient_id -> bed_id) from active BedAssignments ---
    active_assignments = (
        db.query(BedAssignment.bed_id, Encounter.patient_id)
        .join(Encounter, Encounter.encounter_id == BedAssignment.encounter_id)
        .filter(BedAssignment.released_at.is_(None))
        .all()
    )
    state.admitted_patients = {patient_id: bed_id for bed_id, patient_id in active_assignments}

    # --- Simulated clock: use max(arrival_time) so G2 / wait_so_far work correctly ---
    latest_arrival: datetime | None = db.query(func.max(PatientRow.arrival_time)).scalar()
    if latest_arrival is not None:
        # arrival_time is stored without tzinfo; ensure it stays naive
        state.current_time = (
            latest_arrival.replace(tzinfo=None)
            if latest_arrival.tzinfo is not None
            else latest_arrival
        )
    else:
        # Empty DB — fall back to wall-clock UTC (naive)
        state.current_time = datetime.now(timezone.utc).replace(tzinfo=None)

    return state


def to_simulator_patient(row: PatientRow) -> SimPatient:
    return SimPatient(
        patient_id=row.patient_id, age_group=row.age_group, acuity=row.acuity,
        specialty=row.specialty, predicted_los=row.predicted_los,
        isolation_required=row.isolation_required,
        ventilator_required=row.ventilator_required,
        arrival_time=row.arrival_time,
    )
