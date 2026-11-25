import os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.api.auth import router as auth_router

from backend.api.schemas import (
    AllocationRecommendRequest,
    AllocationApproveRequest,
    AllocationRejectRequest,
    DQNAllocationRecommendResponse,
    SurgeSimulationRequest,
    RootResponse,
    PatientsResponse,
    BedsResponse,
    StaffResponse,
    EquipmentResponse,
    AllocationRecommendResponse,
    AllocationApproveResponse,
    SurgeSimulationResponse,
    MetricsResponse,
    AuditResponse,
)
from backend.db.database import get_db
from backend.models import (
    AllocationRecommendation,
    AuditLog,
    Bed,
    Encounter,
    Equipment,
    Patient,
    Staff,
    User,
)
from backend.services.hospital_state import build_hospital_state, to_simulator_patient
from backend.services.patient_lifecycle import (
    LifecycleConflict,
    LifecycleNotFound,
    LifecycleValidationError,
    approve_encounter,
)
from rl.serving.service import AllocationService, BED_ACTIONS
from simulator.patients.patient import Patient as SimulatorPatient

_allocation_service = None

def get_allocation_service() -> AllocationService:
    global _allocation_service
    if _allocation_service is None:
        model_path = os.getenv("ALLOCATION_MODEL_PATH")
        _allocation_service = AllocationService(model_path=model_path)
    return _allocation_service

from pathlib import Path

from simulator.hospital.allocation_rules import candidate_bed_types
from simulator.hospital.loader import load_hospital_state, load_patients
from simulator.hospital.policy import DEFAULT_ALGORITHM, recommend
from simulator.hospital.engine import SimulationEngine
from simulator.metrics.collector import MetricsCollector
from simulator.metrics.summary import compute_metrics

from backend.auth.dependencies import require_roles

app = FastAPI(
    title="CareGrid API",
    description="Backend API for the CareGrid healthcare resource allocation system",
    version="1.0.0",
)

app.include_router(auth_router)


def _persist_recommendation(
    db: Session,
    *,
    patient: Patient,
    response: dict,
    current_user: User,
) -> dict:
    """Save the displayed result before returning it to the caller.

    The request contract supplies a patient ID, not an Encounter ID. Associate
    history only when there is exactly one matching WAITING Encounter; otherwise
    keep encounter_id NULL rather than guessing which admission it belongs to.
    """
    try:
        waiting_encounters = (
            db.query(Encounter.encounter_id)
            .filter(
                Encounter.patient_id == patient.patient_id,
                Encounter.status == "WAITING",
            )
            .all()
        )
        encounter_id = waiting_encounters[0][0] if len(waiting_encounters) == 1 else None
        safety = response.get("safety") or {}
        row = AllocationRecommendation(
            patient_id=patient.patient_id,
            encounter_id=encounter_id,
            algorithm=response["algorithm"],
            status=response["status"],
            recommended_bed_id=response.get("recommended_bed_id"),
            proposed_action=response.get("proposed_action"),
            final_action=response.get("final_action"),
            proposed_bed_type=response.get("proposed_bed_type"),
            final_bed_type=response.get("final_bed_type"),
            safety_overridden=safety.get("overridden"),
            safety_rule_triggered=safety.get("rule_triggered"),
            safety_original_action=safety.get("original_action"),
            safety_reason=safety.get("reason"),
            q_values=response.get("q_values"),
            # ServingResult currently exposes no model version, so this remains NULL.
            model_version=None,
            reason=response["reason"],
            requested_by=current_user.id,
        )
        db.add(row)
        db.flush()
        response["recommendation_id"] = row.recommendation_id
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise

@app.get("/", response_model=RootResponse)
def root():
    return {
        "message": "CareGrid API is running"
    }


@app.get("/patients", response_model=PatientsResponse)
def get_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "doctor", "nurse", "operator")
    ),
):
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


@app.get("/beds", response_model=BedsResponse)
def get_beds(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "doctor", "nurse", "operator")
    ),
):
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

@app.get("/staff", response_model=StaffResponse)
def get_staff(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "operator")
    ),
):
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

@app.get("/equipment", response_model=EquipmentResponse)
def get_equipment(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "nurse", "operator")
    ),
):
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


@app.post("/allocation/recommend", response_model=AllocationRecommendResponse | DQNAllocationRecommendResponse,)
def recommend_allocation(
    request: AllocationRecommendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "doctor")
    ),
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

    # 3. Validate acuity (the shared rules only accept 1-5)
    try:
        candidate_bed_types(patient.acuity)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid patient acuity",
        )

    # 4. Handle requested algorithm
    algo = getattr(request, "algorithm", "rule_based") or "rule_based"
    if algo == "dqn_safe":
        service = get_allocation_service()
        sim_patient = to_simulator_patient(patient)
        sim_state = build_hospital_state(db)
        all_waiting = db.query(Patient).filter(Patient.current_status == "WAITING").all()
        patients_by_id = {p.patient_id: to_simulator_patient(p) for p in all_waiting}
        res = service.recommend(sim_patient, sim_state, patients_by_id=patients_by_id)
        response = {
            "patient_id": patient.patient_id,
            "recommended_bed_id": res.recommended_bed_id,
            "algorithm": res.algorithm,
            "reason": "; ".join(res.reasons) if res.reasons else "",
            "status": res.status,
            "safety": res.safety.to_dict(),
            "q_values": res.q_values,
            "los_estimate_days": res.los_estimate_days,
            "proposed_action": res.proposed_action,
            "final_action": res.final_action,
            "proposed_bed_type": res.proposed_bed_type,
            "final_bed_type": res.final_bed_type,
        }
        return _persist_recommendation(
            db, patient=patient, response=response, current_user=current_user
        )

    # Default: rule-based allocation (same code the simulator uses)
    result = recommend(
        to_simulator_patient(patient),
        build_hospital_state(db),
        DEFAULT_ALGORITHM,
    )

    if result.decision is None:
        response = {
            "patient_id": patient.patient_id,
            "recommended_bed_id": None,
            "algorithm": DEFAULT_ALGORITHM,
            "reason": result.reason,
            "status": "NO_SUITABLE_BED",
        }
        return _persist_recommendation(
            db, patient=patient, response=response, current_user=current_user
        )

    response = {
        "patient_id": patient.patient_id,
        "recommended_bed_id": result.decision.bed_id,
        "algorithm": DEFAULT_ALGORITHM,
        "reason": result.reason,
        "status": "RECOMMENDED",
    }
    return _persist_recommendation(
        db, patient=patient, response=response, current_user=current_user
    )


@app.post("/allocation/reject")
def reject_allocation(
    request: AllocationRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "doctor")
    ),
):
    recommendation = (
        db.query(AllocationRecommendation)
        .filter(AllocationRecommendation.recommendation_id == request.recommendation_id)
        .with_for_update()
        .populate_existing()
        .first()
    )

    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if request.patient_id is not None and request.patient_id != recommendation.patient_id:
        raise HTTPException(
            status_code=409,
            detail="Recommendation does not belong to the specified patient",
        )

    patient = (
        db.query(Patient)
        .filter(Patient.patient_id == recommendation.patient_id)
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

    if any((
        recommendation.decision_status is not None,
        recommendation.decision_reason is not None,
        recommendation.decided_by is not None,
        recommendation.decided_at is not None,
    )):
        raise HTTPException(status_code=409, detail="Recommendation has already been decided")

    if (
        recommendation.status.upper() != "RECOMMENDED"
        or recommendation.recommended_bed_id is None
    ):
        raise HTTPException(status_code=409, detail="Recommendation is not eligible for rejection")

    if recommendation.encounter_id is not None:
        encounter = (
            db.query(Encounter)
            .filter(Encounter.encounter_id == recommendation.encounter_id)
            .with_for_update()
            .first()
        )
        if encounter is None or encounter.status.upper() != "WAITING":
            raise HTTPException(status_code=409, detail="Recommendation Encounter is no longer waiting")

    now = datetime.now(timezone.utc)
    recommendation.decision_status = "REJECTED"
    recommendation.decision_reason = request.reason
    recommendation.decided_by = current_user.id
    recommendation.decided_at = now
    # consumed_at has no defined use in the current workflow; preserve its
    # existing meaning and leave it unchanged while recording operator choice.
    db.add(AuditLog(
        patient_id=patient.patient_id,
        bed_id=recommendation.recommended_bed_id,
        action="REJECTED",
        algorithm="operator_override",
        timestamp=now,
    ))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "recommendation_id": recommendation.recommendation_id,
        "patient_id": patient.patient_id,
        "status": "REJECTED",
        "reason": request.reason,
    }


@app.post("/allocation/approve", response_model=AllocationApproveResponse)
def approve_allocation(
    request: AllocationApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "doctor")
    ),
):
    recommendation = (
        db.query(AllocationRecommendation)
        .filter(AllocationRecommendation.recommendation_id == request.recommendation_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if request.patient_id is not None and request.patient_id != recommendation.patient_id:
        raise HTTPException(
            status_code=409,
            detail="Recommendation does not belong to the specified patient",
        )

    if request.bed_id is not None and request.bed_id != recommendation.recommended_bed_id:
        raise HTTPException(
            status_code=409,
            detail="Requested bed does not match the persisted recommendation",
        )

    if (
        recommendation.decision_status is not None
        or recommendation.decision_reason is not None
        or recommendation.decided_by is not None
        or recommendation.decided_at is not None
    ):
        raise HTTPException(
            status_code=409,
            detail="Recommendation has already been decided",
        )

    if recommendation.consumed_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Recommendation has already been consumed",
        )

    if recommendation.status.upper() != "RECOMMENDED":
        raise HTTPException(status_code=409, detail="Recommendation is not successful")
    if recommendation.recommended_bed_id is None:
        raise HTTPException(status_code=409, detail="Recommendation has no bed to approve")
    if recommendation.encounter_id is None:
        raise HTTPException(
            status_code=409,
            detail="Recommendation is not linked to an Encounter; request a new recommendation",
        )

    patient = db.query(Patient).filter(
        Patient.patient_id == recommendation.patient_id
    ).first()
    encounter = db.query(Encounter).filter(
        Encounter.encounter_id == recommendation.encounter_id
    ).first()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    if encounter is None:
        raise HTTPException(status_code=409, detail="Recommendation Encounter no longer exists")
    if encounter.patient_id != recommendation.patient_id:
        raise HTTPException(status_code=409, detail="Encounter belongs to a different patient")
    if encounter.status.upper() != "WAITING":
        raise HTTPException(status_code=409, detail="Encounter is no longer waiting for allocation")
    if patient.current_status.upper() != "WAITING":
        raise HTTPException(status_code=409, detail="Patient is not waiting for allocation")

    if recommendation.algorithm not in {"rule_based", "dqn_safe", "rule_based_fallback"}:
        raise HTTPException(status_code=409, detail="Recommendation algorithm is not supported for approval")

    if recommendation.algorithm == "dqn_safe":
        if (
            recommendation.proposed_action is None
            or recommendation.final_action is None
            or recommendation.safety_overridden is None
            or recommendation.safety_original_action != recommendation.proposed_action
        ):
            raise HTTPException(status_code=409, detail="DQN recommendation safety metadata is incomplete")

        arrival_time = encounter.arrival_time
        if arrival_time.tzinfo is not None:
            arrival_time = arrival_time.astimezone(timezone.utc).replace(tzinfo=None)
        sim_patient = SimulatorPatient(
            patient_id=patient.patient_id,
            age_group=patient.age_group,
            acuity=encounter.acuity,
            specialty=encounter.specialty,
            predicted_los=encounter.predicted_los,
            isolation_required=encounter.isolation_required,
            ventilator_required=encounter.ventilator_required,
            arrival_time=arrival_time,
        )
        safety_decision = get_allocation_service().safety_layer.review(
            sim_patient,
            build_hospital_state(db),
            recommendation.proposed_action,
        )
        current_safety_reason = "; ".join(safety_decision.reason_codes) or None
        if (
            safety_decision.final_action != recommendation.final_action
            or safety_decision.was_overridden != recommendation.safety_overridden
            or safety_decision.guardrail_triggered != recommendation.safety_rule_triggered
            or current_safety_reason != recommendation.safety_reason
        ):
            raise HTTPException(status_code=409, detail="DQN recommendation failed current safety validation")
        if not 0 <= safety_decision.final_action < len(BED_ACTIONS):
            raise HTTPException(status_code=409, detail="DQN recommendation does not resolve to a bed")
        expected_bed_type = BED_ACTIONS[safety_decision.final_action]
        current_bed_type = db.query(Bed.bed_type).filter(
            Bed.bed_id == recommendation.recommended_bed_id
        ).scalar()
        if current_bed_type is None:
            raise HTTPException(status_code=404, detail="Recommended bed not found")
        if recommendation.final_bed_type != expected_bed_type or current_bed_type != expected_bed_type:
            raise HTTPException(status_code=409, detail="DQN recommendation bed no longer matches its safe action")

    now = datetime.now(timezone.utc)
    try:
        admitted_encounter = approve_encounter(
            db,
            encounter.encounter_id,
            recommendation.recommended_bed_id,
            actor_id=current_user.id,
        )

        # Claim the decision only after lifecycle validation and resource writes
        # succeed. The predicate is an additional guard against duplicate use
        # on databases where row-lock semantics are limited.
        claimed = db.execute(
            update(AllocationRecommendation)
            .where(
                AllocationRecommendation.recommendation_id == recommendation.recommendation_id,
                AllocationRecommendation.decision_status.is_(None),
                AllocationRecommendation.decision_reason.is_(None),
                AllocationRecommendation.decided_by.is_(None),
                AllocationRecommendation.decided_at.is_(None),
                AllocationRecommendation.consumed_at.is_(None),
                AllocationRecommendation.status == "RECOMMENDED",
                AllocationRecommendation.recommended_bed_id == recommendation.recommended_bed_id,
                AllocationRecommendation.encounter_id == admitted_encounter.encounter_id,
            )
            .values(
                decision_status="APPROVED",
                decided_by=current_user.id,
                decided_at=now,
            )
        )
        if claimed.rowcount != 1:
            raise LifecycleConflict("Recommendation has already been decided or consumed")

        db.add(AuditLog(
            patient_id=admitted_encounter.patient_id,
            bed_id=recommendation.recommended_bed_id,
            action="APPROVED",
            algorithm=recommendation.algorithm,
            timestamp=now,
        ))
        db.commit()
    except LifecycleNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LifecycleValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LifecycleConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Approval conflicts with current resource assignments") from exc
    except Exception:
        db.rollback()
        raise

    return {
        "patient_id": admitted_encounter.patient_id,
        "bed_id": recommendation.recommended_bed_id,
        "status": "APPROVED",
    }

@app.post("/surge/simulate", response_model=SurgeSimulationResponse)
def simulate_surge(
    request: SurgeSimulationRequest,
    current_user: User = Depends(
        require_roles("admin", "operator")
    ),
):
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


@app.get("/metrics", response_model=MetricsResponse)
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "doctor", "nurse", "operator")
    ),
):
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




@app.get("/audit", response_model=AuditResponse)
def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("admin", "operator")
    ),
):
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
