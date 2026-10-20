from datetime import datetime, timedelta, timezone
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from backend.api.schemas import (
    AllocationRecommendRequest,
    AllocationApproveRequest,
    SurgeSimulationRequest,
)
from backend.db.database import get_db
from backend.models import AuditLog, Bed, Equipment, Patient, Staff

from pathlib import Path

from simulator.hospital.loader import load_hospital_state, load_patients
from simulator.hospital.engine import SimulationEngine
from simulator.metrics.collector import MetricsCollector
from simulator.metrics.summary import compute_metrics


app = FastAPI(
    title="CareGrid API",
    description="Backend API for the CareGrid healthcare resource allocation system",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "CareGrid API is running"
    }


@app.get("/patients")
def get_patients(db: Session = Depends(get_db)):
    patients = db.query(Patient).all()

    return {
        "patients": [
            {
                "patient_id": patient.patient_id,
                "age_group": patient.age_group,
                "acuity": patient.acuity,
                "specialty": patient.specialty,
                "predicted_los": patient.predicted_los,
                "isolation_required": patient.isolation_required,
                "ventilator_required": patient.ventilator_required,
                "arrival_time": patient.arrival_time,
                "current_status": patient.current_status,
            }
            for patient in patients
        ]
    }


@app.get("/beds")
def get_beds(db: Session = Depends(get_db)):
    beds = db.query(Bed).all()

    return {
        "beds": [
            {
                "bed_id": bed.bed_id,
                "bed_type": bed.bed_type,
                "ward": bed.ward,
                "status": bed.status,
                "isolation_capable": bed.isolation_capable,
            }
            for bed in beds
        ]
    }

@app.get("/staff")
def get_staff(db: Session = Depends(get_db)):
    staff_members = db.query(Staff).all()

    return {
        "staff": [
            {
                "staff_id": member.staff_id,
                "role": member.role,
                "skill_level": member.skill_level,
                "shift": member.shift,
                "workload": member.workload,
            }
            for member in staff_members
        ]
    }

@app.get("/equipment")
def get_equipment(db: Session = Depends(get_db)):
    equipment_items = db.query(Equipment).all()

    return {
        "equipment": [
            {
                "equipment_id": item.equipment_id,
                "type": item.type,
                "status": item.status,
                "location": item.location,
            }
            for item in equipment_items
        ]
    }


@app.post("/allocation/recommend")
def recommend_allocation(
    request: AllocationRecommendRequest,
    db: Session = Depends(get_db),
):
    # 1. Find the patient
    patient = db.query(Patient).filter(
        Patient.patient_id == request.patient_id
    ).first()

    if patient is None:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    # 2. Only waiting patients can receive recommendations
    if patient.current_status.upper() != "WAITING":
        raise HTTPException(
            status_code=409,
            detail="Patient is not waiting for allocation",
        )

    # 3. Define bed preference according to simulator rules
    bed_preferences = {
        5: ["ICU"],
        4: ["ICU", "STEP_DOWN"],
        3: ["STEP_DOWN", "WARD"],
        2: ["WARD"],
        1: ["WARD"],
    }

    preferred_types = bed_preferences.get(patient.acuity)

    if preferred_types is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid patient acuity",
        )

    # 4. Find available beds
    available_beds = (
        db.query(Bed)
        .filter(Bed.status == "AVAILABLE")
        .all()
    )

    # 5. Find an available ventilator if required
    if patient.ventilator_required:
        available_ventilator = (
            db.query(Equipment)
            .filter(
                Equipment.type == "VENTILATOR",
                Equipment.status == "AVAILABLE",
            )
            .order_by(Equipment.equipment_id)
            .first()
        )

        if available_ventilator is None:
            return {
                "patient_id": patient.patient_id,
                "recommended_bed_id": None,
                "algorithm": "rule_based",
                "reason": "No available ventilator",
                "status": "NO_SUITABLE_BED",
            }

    # 6. Select the first eligible bed in preference order
    for bed_type in preferred_types:
        candidates = [
            bed for bed in available_beds
            if bed.bed_type == bed_type
            and (
                not patient.isolation_required
                or bed.isolation_capable
            )
        ]

        if candidates:
            chosen_bed = min(
                candidates,
                key=lambda bed: bed.bed_id,
            )

            return {
                "patient_id": patient.patient_id,
                "recommended_bed_id": chosen_bed.bed_id,
                "algorithm": "rule_based",
                "reason": (
                    f"Compatible {bed_type} bed available"
                ),
                "status": "RECOMMENDED",
            }

    # 7. No compatible bed found
    return {
        "patient_id": patient.patient_id,
        "recommended_bed_id": None,
        "algorithm": "rule_based",
        "reason": "No compatible available bed found",
        "status": "NO_SUITABLE_BED",
    }



@app.post("/allocation/approve")
def approve_allocation(
    request: AllocationApproveRequest,
    db: Session = Depends(get_db),
):
    # 1. Find the patient
    patient = (
        db.query(Patient)
        .filter(Patient.patient_id == request.patient_id)
        .with_for_update()
        .first()
    )

    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    if patient.current_status.upper() != "WAITING":
        raise HTTPException(
            status_code=409,
            detail="Patient is not waiting for allocation",
        )

    # 2. Lock and validate the requested bed
    bed = (
        db.query(Bed)
        .filter(Bed.bed_id == request.bed_id)
        .with_for_update()
        .first()
    )

    if bed is None:
        raise HTTPException(status_code=404, detail="Bed not found")

    if bed.status.upper() != "AVAILABLE":
        raise HTTPException(
            status_code=409,
            detail="Bed is no longer available",
        )

    # 3. Validate the bed type against patient acuity
    bed_preferences = {
        5: ["ICU"],
        4: ["ICU", "STEP_DOWN"],
        3: ["STEP_DOWN", "WARD"],
        2: ["WARD"],
        1: ["WARD"],
    }

    preferred_types = bed_preferences.get(patient.acuity)

    if preferred_types is None:
        raise HTTPException(status_code=400, detail="Invalid patient acuity")

    if bed.bed_type not in preferred_types:
        raise HTTPException(
            status_code=400,
            detail="Bed type is incompatible with patient acuity",
        )

    # 4. Validate isolation requirement
    if patient.isolation_required and not bed.isolation_capable:
        raise HTTPException(
            status_code=400,
            detail="Patient requires an isolation-capable bed",
        )

    # 5. Reserve a ventilator if required
    ventilator = None

    if patient.ventilator_required:
        ventilator = (
            db.query(Equipment)
            .filter(
                Equipment.type == "VENTILATOR",
                Equipment.status == "AVAILABLE",
            )
            .order_by(Equipment.equipment_id)
            .with_for_update()
            .first()
        )

        if ventilator is None:
            raise HTTPException(
                status_code=409,
                detail="No available ventilator",
            )

    # 6. Update everything in one transaction
    try:
        bed.status = "OCCUPIED"

        if ventilator is not None:
            ventilator.status = "IN_USE"

        patient.current_status = "ADMITTED"

        audit_entry = AuditLog(
        patient_id=patient.patient_id,
        bed_id=bed.bed_id,
        action="APPROVED",
        algorithm="rule_based",
        timestamp=datetime.now(timezone.utc),
        )
        db.add(audit_entry)

        db.commit()

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Allocation failed; changes were rolled back",
        )

    return {
        "patient_id": patient.patient_id,
        "bed_id": bed.bed_id,
        "status": "APPROVED",
    }

@app.post("/surge/simulate")
def simulate_surge(request: SurgeSimulationRequest):
    try:
        # Resolve the dataset directory from the project root.
        data_dir = Path(__file__).resolve().parents[2] / "data" / "synthetic"

        # Load fresh in-memory state and patient objects.
        state = load_hospital_state(data_dir)
        patients = load_patients(data_dir)

        if not patients:
            raise HTTPException(
                status_code=500,
                detail="No patients were loaded for simulation.",
            )

        # Start the simulation at the earliest patient arrival.
        original_start = min(p.arrival_time for p in patients)
        window_start = original_start
        window_end = window_start + timedelta(hours=request.duration_hours)

        # Compress or expand arrival offsets around the original start.
        multiplier = request.arrival_rate_multiplier
        for patient in patients:
            offset = patient.arrival_time - original_start
            patient.arrival_time = original_start + offset / multiplier

        # Collect measurements across the requested simulation window.
        collector = MetricsCollector(window_start, window_end)
        engine = SimulationEngine(state, patients)
        engine.seed_arrivals()
        engine.run(max_time=window_end, on_tick=collector.on_tick)

        # Account for the interval between the last event and window end.
        state.current_time = window_end
        collector.on_tick(state)

        patients_arrived = sum(
        1 for patient in patients
        if patient.arrival_time <= window_end
    )

        metrics = compute_metrics(engine, collector)
        waiting_patients = [
        patient
        for patient in engine.patients.values()
        if patient.status == "WAITING"
        and patient.arrival_time <= window_end
    ]

        elapsed_waits = [
            (window_end - patient.arrival_time).total_seconds() / 60
            for patient in waiting_patients
        ]

        metrics["waiting_patients_elapsed_wait_min"] = {
            "avg": round(sum(elapsed_waits) / len(elapsed_waits), 2)
            if elapsed_waits else 0.0,
            "max": round(max(elapsed_waits), 2)
            if elapsed_waits else 0.0,
        }

        return {
            "status": "COMPLETED",
            "arrival_rate_multiplier": multiplier,
            "duration_hours": request.duration_hours,
            "patients_arrived": patients_arrived,
            "simulation_start": window_start.isoformat(),
            "simulation_end": window_end.isoformat(),
            "metrics": metrics,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Surge simulation failed: {exc}",
        ) from exc


@app.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    # Patient counts
    patients_total = db.query(Patient).count()
    patients_waiting = (
        db.query(Patient)
        .filter(Patient.current_status == "WAITING")
        .count()
    )
    patients_admitted = (
        db.query(Patient)
        .filter(Patient.current_status == "ADMITTED")
        .count()
    )

    # Bed counts
    beds_total = db.query(Bed).count()
    beds_available = (
        db.query(Bed)
        .filter(Bed.status == "AVAILABLE")
        .count()
    )
    beds_occupied = (
        db.query(Bed)
        .filter(Bed.status == "OCCUPIED")
        .count()
    )

    # Avoid division by zero
    bed_occupancy_rate = (
        round(beds_occupied / beds_total, 4)
        if beds_total
        else 0.0
    )

    # Ventilator availability
    ventilators_total = (
        db.query(Equipment)
        .filter(Equipment.type == "VENTILATOR")
        .count()
    )
    ventilators_available = (
        db.query(Equipment)
        .filter(
            Equipment.type == "VENTILATOR",
            Equipment.status == "AVAILABLE",
        )
        .count()
    )
    ventilators_in_use = (
        db.query(Equipment)
        .filter(
            Equipment.type == "VENTILATOR",
            Equipment.status == "IN_USE",
        )
        .count()
    )

    # Successful allocation audit records
    approved_allocations = (
        db.query(AuditLog)
        .filter(AuditLog.action == "APPROVED")
        .count()
    )

    return {
        "patients_total": patients_total,
        "patients_waiting": patients_waiting,
        "patients_admitted": patients_admitted,
        "beds_total": beds_total,
        "beds_available": beds_available,
        "beds_occupied": beds_occupied,
        "bed_occupancy_rate": bed_occupancy_rate,
        "ventilators_total": ventilators_total,
        "ventilators_available": ventilators_available,
        "ventilators_in_use": ventilators_in_use,
        "approved_allocations": approved_allocations,
    }




@app.get("/audit")
def get_audit_logs(db: Session = Depends(get_db)):
    records = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(100)
        .all()
    )

    return {
        "audit": [
            {
                "patient_id": record.patient_id,
                "bed_id": record.bed_id,
                "action": record.action,
                "algorithm": record.algorithm,
                "timestamp": record.timestamp.isoformat(),
            }
            for record in records
        ]
    }
