import os
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import Body, Depends, FastAPI, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.api.auth import router as auth_router

from backend.api.schemas import (
    AllocationRecommendRequest,
    AllocationApproveRequest,
    AllocationRejectRequest,
    BedCleaningResponse,
    BedCreateRequest,
    BedCreateResponse,
    BedReleaseResponse,
    DischargeRequest,
    DischargeResponse,
    DQNAllocationRecommendResponse,
    EquipmentAssignmentResponse,
    EquipmentAssignRequest,
    EquipmentReleaseRequest,
    PatientIntakeRequest,
    PatientIntakeResponse,
    SurgeSimulationRequest,
    TransferRequest,
    TransferResponse,
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
    BedAssignment,
    Encounter,
    Equipment,
    EquipmentAssignment,
    Patient,
    Staff,
    User,
)
from backend.services.hospital_state import build_hospital_state, to_simulator_patient
from backend.services.patient_lifecycle import (
    LifecycleConflict,
    LifecycleError,
    LifecycleNotFound,
    LifecycleValidationError,
    approve_encounter,
    assign_equipment as lifecycle_assign_equipment,
    complete_bed_cleaning,
    create_encounter,
    discharge_encounter,
    release_equipment as lifecycle_release_equipment,
    transfer_encounter,
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

from backend.auth.dependencies import require_permission, require_roles

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
def _raise_lifecycle_http_error(exc: LifecycleError) -> None:
    if isinstance(exc, LifecycleNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, LifecycleConflict):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, LifecycleValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def _generate_patient_id(db: Session) -> str:
    existing_ids = set(db.scalars(select(Patient.patient_id)).all())
    max_num = 0
    for pid in existing_ids:
        if pid.startswith("P") and pid[1:].isdigit():
            max_num = max(max_num, int(pid[1:]))
    candidate = f"P{max_num + 1:04d}"
    if len(candidate) <= 10 and candidate not in existing_ids:
        return candidate
    for _ in range(10):
        fallback = f"P{uuid.uuid4().hex[:9].upper()}"
        if fallback not in existing_ids:
            return fallback
    raise HTTPException(status_code=500, detail="Unable to generate unique patient ID")


def _resolve_target_encounter(
    db: Session,
    *,
    patient_id: str | None = None,
    encounter_id: int | None = None,
) -> Encounter:
    if encounter_id is not None:
        encounter = db.get(Encounter, encounter_id)
        if encounter is None:
            raise HTTPException(status_code=404, detail="Encounter not found")
        if patient_id is not None and encounter.patient_id != patient_id:
            raise HTTPException(
                status_code=400,
                detail="Encounter does not belong to the specified patient",
            )
        return encounter

    if patient_id is None:
        raise HTTPException(
            status_code=422,
            detail="Either patient_id or encounter_id must be provided",
        )

    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    encounter = db.execute(
        select(Encounter)
        .where(
            Encounter.patient_id == patient_id,
            Encounter.status == "ADMITTED",
        )
        .order_by(Encounter.encounter_id.desc())
    ).scalar_one_or_none()
    if encounter is None:
        raise HTTPException(
            status_code=409,
            detail="Patient has no active admitted encounter",
        )
    return encounter

@app.get("/", response_model=RootResponse)
def root():
    return {
        "message": "CareGrid API is running"
    }


@app.get("/patients", response_model=PatientsResponse)
def get_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("patients:read")),
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


@app.post("/patients/intake", response_model=PatientIntakeResponse, status_code=201)
def intake_patient(
    request: PatientIntakeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("patients:intake")),
):
    arrival_time = request.arrival_time or datetime.now(timezone.utc)
    patient_id = request.patient_id or _generate_patient_id(db)

    try:
        patient = db.execute(
            select(Patient).where(Patient.patient_id == patient_id).with_for_update()
        ).scalar_one_or_none()

        if patient is None:
            patient = Patient(
                patient_id=patient_id,
                age_group=request.age_group,
                acuity=request.acuity,
                specialty=request.specialty,
                predicted_los=request.predicted_los,
                isolation_required=request.isolation_required,
                ventilator_required=request.ventilator_required,
                arrival_time=arrival_time,
                current_status="WAITING",
            )
            db.add(patient)
            db.flush()
        else:
            if patient.current_status.upper() in ("WAITING", "ADMITTED"):
                raise LifecycleConflict("Patient already has an active waiting or admitted status")
            patient.age_group = request.age_group
            patient.acuity = request.acuity
            patient.specialty = request.specialty
            patient.predicted_los = request.predicted_los
            patient.isolation_required = request.isolation_required
            patient.ventilator_required = request.ventilator_required
            patient.arrival_time = arrival_time

        encounter = create_encounter(
            db,
            patient.patient_id,
            acuity=request.acuity,
            specialty=request.specialty,
            predicted_los=request.predicted_los,
            isolation_required=request.isolation_required,
            ventilator_required=request.ventilator_required,
            arrival_time=arrival_time,
        )
        db.commit()
        db.refresh(patient)
        db.refresh(encounter)
    except LifecycleError as exc:
        db.rollback()
        _raise_lifecycle_http_error(exc)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Patient intake failed; changes were rolled back",
        ) from exc

    return {
        "patient_id": patient.patient_id,
        "encounter_id": encounter.encounter_id,
        "age_group": patient.age_group,
        "acuity": encounter.acuity,
        "specialty": encounter.specialty,
        "predicted_los": encounter.predicted_los,
        "isolation_required": encounter.isolation_required,
        "ventilator_required": encounter.ventilator_required,
        "arrival_time": encounter.arrival_time,
        "current_status": patient.current_status,
        "encounter_status": encounter.status,
    }


def _perform_discharge(
    db: Session,
    encounter: Encounter,
    current_user: User,
    request: DischargeRequest,
) -> dict:
    try:
        active_bed = db.execute(
            select(BedAssignment).where(
                BedAssignment.encounter_id == encounter.encounter_id,
                BedAssignment.released_at.is_(None),
            )
        ).scalar_one_or_none()
        active_equipment_ids = db.execute(
            select(EquipmentAssignment.equipment_id)
            .where(
                EquipmentAssignment.encounter_id == encounter.encounter_id,
                EquipmentAssignment.released_at.is_(None),
            )
            .order_by(EquipmentAssignment.equipment_id)
        ).scalars().all()

        discharged = discharge_encounter(
            db,
            encounter.encounter_id,
            actor_id=current_user.id,
            release_reason=request.release_reason,
        )
        db.commit()
        db.refresh(discharged)
        patient = db.get(Patient, discharged.patient_id)
        bed = db.get(Bed, active_bed.bed_id) if active_bed is not None else None
    except LifecycleError as exc:
        db.rollback()
        _raise_lifecycle_http_error(exc)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Discharge failed; changes were rolled back",
        ) from exc

    return {
        "patient_id": discharged.patient_id,
        "encounter_id": discharged.encounter_id,
        "bed_id": bed.bed_id if bed is not None else "",
        "bed_status": bed.status if bed is not None else "",
        "released_equipment_ids": list(active_equipment_ids),
        "patient_status": patient.current_status if patient is not None else discharged.status,
        "encounter_status": discharged.status,
        "discharged_at": discharged.discharged_at,
    }


@app.post("/patients/{patient_id}/discharge", response_model=DischargeResponse)
def discharge_patient(
    patient_id: str,
    request: DischargeRequest = Body(default_factory=DischargeRequest),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("patients:discharge")),
):
    encounter = _resolve_target_encounter(
        db,
        patient_id=patient_id,
        encounter_id=request.encounter_id,
    )
    return _perform_discharge(db, encounter, current_user, request)


@app.post("/encounters/{encounter_id}/discharge", response_model=DischargeResponse)
def discharge_encounter_endpoint(
    encounter_id: int,
    request: DischargeRequest = Body(default_factory=DischargeRequest),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("patients:discharge")),
):
    encounter = _resolve_target_encounter(db, encounter_id=encounter_id)
    return _perform_discharge(db, encounter, current_user, request)


def _perform_transfer(
    db: Session,
    encounter: Encounter,
    current_user: User,
    request: TransferRequest,
) -> dict:
    try:
        active_bed = db.execute(
            select(BedAssignment).where(
                BedAssignment.encounter_id == encounter.encounter_id,
                BedAssignment.released_at.is_(None),
            )
        ).scalar_one_or_none()
        from_bed_id = active_bed.bed_id if active_bed is not None else ""

        transferred = transfer_encounter(
            db,
            encounter.encounter_id,
            request.destination_bed_id,
            actor_id=current_user.id,
            release_reason=request.release_reason,
        )
        db.commit()
    except LifecycleError as exc:
        db.rollback()
        _raise_lifecycle_http_error(exc)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Transfer failed; changes were rolled back",
        ) from exc

    return {
        "patient_id": transferred.patient_id,
        "encounter_id": transferred.encounter_id,
        "from_bed_id": from_bed_id,
        "to_bed_id": request.destination_bed_id,
        "status": "TRANSFERRED",
    }


@app.post("/patients/{patient_id}/transfer", response_model=TransferResponse)
def transfer_patient(
    patient_id: str,
    request: TransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("patients:transfer")),
):
    encounter = _resolve_target_encounter(
        db,
        patient_id=patient_id,
        encounter_id=request.encounter_id,
    )
    return _perform_transfer(db, encounter, current_user, request)


@app.post("/encounters/{encounter_id}/transfer", response_model=TransferResponse)
def transfer_encounter_endpoint(
    encounter_id: int,
    request: TransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("patients:transfer")),
):
    encounter = _resolve_target_encounter(db, encounter_id=encounter_id)
    return _perform_transfer(db, encounter, current_user, request)


@app.get("/beds", response_model=BedsResponse)
def get_beds(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("beds:read")),
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


@app.post("/beds", response_model=BedCreateResponse, status_code=201)
def create_bed(
    request: BedCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("beds:create")),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators may create beds")
    try:
        if db.get(Bed, request.bed_id) is not None:
            raise HTTPException(status_code=409, detail="Bed ID already exists")
        bed = Bed(
            bed_id=request.bed_id,
            bed_type=request.bed_type,
            ward=request.ward,
            status="AVAILABLE",
            isolation_capable=request.isolation_capable,
        )
        db.add(bed)
        db.flush()
        db.add(AuditLog(patient_id=None, bed_id=bed.bed_id, action="BED_CREATED", algorithm="api"))
        db.commit()
        db.refresh(bed)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bed ID already exists") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Bed creation failed; changes were rolled back") from exc
    return {"message": "Bed created successfully", "bed": bed}


@app.post("/beds/{bed_id}/empty", response_model=BedReleaseResponse)
def empty_bed(
    bed_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("beds:release")),
):
    bed = db.get(Bed, bed_id)
    if bed is None:
        raise HTTPException(status_code=404, detail="Bed not found")
    if bed.status.upper() == "AVAILABLE":
        raise HTTPException(status_code=409, detail="Bed is already available")
    if bed.status.upper() == "CLEANING":
        raise HTTPException(status_code=409, detail="Bed is already awaiting cleaning")
    assignment = db.execute(select(BedAssignment).where(
        BedAssignment.bed_id == bed_id, BedAssignment.released_at.is_(None)
    )).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=409, detail="Occupied bed has no active patient assignment")
    encounter = db.get(Encounter, assignment.encounter_id)
    if encounter is not None and encounter.status.upper() == "ADMITTED":
        raise HTTPException(status_code=409, detail="Active patient encounter prevents release; discharge or transfer the patient first")
    raise HTTPException(status_code=409, detail="Bed release must be performed by the discharge or transfer workflow; no eligible release operation exists")


@app.post("/beds/{bed_id}/cleaning-complete", response_model=BedCleaningResponse)
def complete_bed_cleaning_endpoint(
    bed_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("beds:clean")),
):
    try:
        bed = complete_bed_cleaning(db, bed_id)
        db.commit()
        db.refresh(bed)
    except LifecycleError as exc:
        db.rollback()
        _raise_lifecycle_http_error(exc)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Bed cleaning completion failed; changes were rolled back",
        ) from exc

    return {
        "bed_id": bed.bed_id,
        "status": bed.status,
    }


@app.get("/staff", response_model=StaffResponse)
def get_staff(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("staff:read")),
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
    current_user: User = Depends(require_permission("equipment:read")),
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


@app.post("/equipment/{equipment_id}/assign", response_model=EquipmentAssignmentResponse)
def assign_equipment_endpoint(
    equipment_id: str,
    request: EquipmentAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("equipment:assign")),
):
    encounter = _resolve_target_encounter(
        db,
        patient_id=request.patient_id,
        encounter_id=request.encounter_id,
    )
    try:
        assignment = lifecycle_assign_equipment(
            db,
            encounter.encounter_id,
            equipment_id,
            actor_id=current_user.id,
        )
        db.commit()
        db.refresh(assignment)
        item = db.get(Equipment, equipment_id)
    except LifecycleError as exc:
        db.rollback()
        _raise_lifecycle_http_error(exc)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Equipment assignment failed; changes were rolled back",
        ) from exc

    return {
        "assignment_id": assignment.assignment_id,
        "encounter_id": assignment.encounter_id,
        "patient_id": encounter.patient_id,
        "equipment_id": assignment.equipment_id,
        "status": item.status if item is not None else "IN_USE",
        "assigned_at": assignment.assigned_at,
        "released_at": assignment.released_at,
        "release_reason": assignment.release_reason,
    }


@app.post("/equipment/{equipment_id}/release", response_model=EquipmentAssignmentResponse)
def release_equipment_endpoint(
    equipment_id: str,
    request: EquipmentReleaseRequest = Body(default_factory=EquipmentReleaseRequest),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("equipment:release")),
):
    if request.patient_id is not None or request.encounter_id is not None:
        encounter = _resolve_target_encounter(
            db,
            patient_id=request.patient_id,
            encounter_id=request.encounter_id,
        )
    else:
        item = db.get(Equipment, equipment_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Equipment {equipment_id} not found")
        active_assignment = db.execute(
            select(EquipmentAssignment).where(
                EquipmentAssignment.equipment_id == equipment_id,
                EquipmentAssignment.released_at.is_(None),
            )
        ).scalar_one_or_none()
        if active_assignment is None:
            raise HTTPException(
                status_code=409,
                detail="No active equipment assignment exists for this equipment",
            )
        encounter = db.get(Encounter, active_assignment.encounter_id)
        if encounter is None:
            raise HTTPException(status_code=404, detail="Encounter not found")

    try:
        assignment = lifecycle_release_equipment(
            db,
            encounter.encounter_id,
            equipment_id,
            release_reason=request.release_reason,
        )
        db.commit()
        db.refresh(assignment)
        item = db.get(Equipment, equipment_id)
    except LifecycleError as exc:
        db.rollback()
        _raise_lifecycle_http_error(exc)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Equipment release failed; changes were rolled back",
        ) from exc

    return {
        "assignment_id": assignment.assignment_id,
        "encounter_id": assignment.encounter_id,
        "patient_id": encounter.patient_id,
        "equipment_id": assignment.equipment_id,
        "status": item.status if item is not None else "AVAILABLE",
        "assigned_at": assignment.assigned_at,
        "released_at": assignment.released_at,
        "release_reason": assignment.release_reason,
    }


@app.post("/allocation/recommend", response_model=AllocationRecommendResponse | DQNAllocationRecommendResponse,)
def recommend_allocation(
    request: AllocationRecommendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("allocation:recommend")),
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
    current_user: User = Depends(require_permission("allocation:reject")),
):
    try:
        recommendation_id = request.recommendation_id
        if recommendation_id is None:
            # Legacy patient-only requests are accepted only when there is exactly
            # one eligible recommendation to identify. Keep lookup order aligned
            # with ID-based requests: recommendation first, then patient.
            patient = db.get(Patient, request.patient_id)
            if patient is None:
                raise HTTPException(status_code=404, detail="Patient not found")
            if patient.current_status.upper() != "WAITING":
                raise HTTPException(
                    status_code=409,
                    detail="Patient is not waiting for allocation",
                )
            candidate_ids = db.query(AllocationRecommendation.recommendation_id).filter(
                AllocationRecommendation.patient_id == request.patient_id,
                AllocationRecommendation.status == "RECOMMENDED",
                AllocationRecommendation.recommended_bed_id.is_not(None),
                AllocationRecommendation.decision_status.is_(None),
                AllocationRecommendation.decision_reason.is_(None),
                AllocationRecommendation.decided_by.is_(None),
                AllocationRecommendation.decided_at.is_(None),
                AllocationRecommendation.consumed_at.is_(None),
            ).all()
            if len(candidate_ids) != 1:
                raise HTTPException(
                    status_code=409,
                    detail="A unique recommendation_id is required to reject this recommendation",
                )
            recommendation_id = candidate_ids[0][0]

        recommendation = (
            db.query(AllocationRecommendation)
            .filter(AllocationRecommendation.recommendation_id == recommendation_id)
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
            .populate_existing()
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
        )) or recommendation.consumed_at is not None:
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
                .populate_existing()
                .first()
            )
            if (
                encounter is None
                or encounter.patient_id != recommendation.patient_id
                or encounter.status.upper() != "WAITING"
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Recommendation Encounter is no longer waiting",
                )

        now = datetime.now(timezone.utc)
        recommendation.decision_status = "REJECTED"
        recommendation.decision_reason = request.reason
        recommendation.decided_by = current_user.id
        recommendation.decided_at = now
        # consumed_at has no defined use in the current workflow; leave it unchanged.
        db.add(AuditLog(
            patient_id=patient.patient_id,
            bed_id=recommendation.recommended_bed_id,
            action="REJECTED",
            algorithm="operator_override",
            timestamp=now,
        ))
        db.commit()
    except HTTPException:
        db.rollback()
        raise
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
    current_user: User = Depends(require_permission("allocation:approve")),
):
    try:
        legacy_operator_override = request.recommendation_id is None
        if legacy_operator_override:
            # Preserve the old patient_id + bed_id request safely by turning it
            # into an explicit, persisted operator override. The lifecycle service
            # still validates availability, acuity, isolation, and equipment.
            patient = (
                db.query(Patient)
                .filter(Patient.patient_id == request.patient_id)
                .with_for_update()
                .populate_existing()
                .first()
            )
            if patient is None:
                raise HTTPException(status_code=404, detail="Patient not found")
            if patient.current_status.upper() != "WAITING":
                raise HTTPException(status_code=409, detail="Patient is not waiting for allocation")

            if request.encounter_id is not None:
                encounter = (
                    db.query(Encounter)
                    .filter(Encounter.encounter_id == request.encounter_id)
                    .with_for_update()
                    .populate_existing()
                    .first()
                )
                if encounter is None:
                    raise LifecycleNotFound("Encounter not found")
                if encounter.patient_id != patient.patient_id:
                    raise LifecycleValidationError(
                        "Encounter does not belong to the specified patient"
                    )
                if encounter.status.upper() != "WAITING":
                    raise LifecycleConflict("Encounter is no longer waiting for allocation")
            else:
                encounter = (
                    db.query(Encounter)
                    .filter(
                        Encounter.patient_id == patient.patient_id,
                        Encounter.status == "WAITING",
                    )
                    .order_by(Encounter.encounter_id.desc())
                    .with_for_update()
                    .first()
                )
                if encounter is None:
                    encounter = create_encounter(db, patient.patient_id)

            recommendation = AllocationRecommendation(
                patient_id=patient.patient_id,
                encounter_id=encounter.encounter_id,
                algorithm="operator_override",
                status="RECOMMENDED",
                recommended_bed_id=request.bed_id,
                reason="Operator-selected bed through the legacy approval request",
                requested_by=current_user.id,
            )
            db.add(recommendation)
            db.flush()
        else:
            recommendation = (
                db.query(AllocationRecommendation)
                .filter(
                    AllocationRecommendation.recommendation_id == request.recommendation_id
                )
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
            request.encounter_id is not None
            and request.encounter_id != recommendation.encounter_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Requested Encounter does not match the persisted recommendation",
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
        if recommendation.algorithm not in {
            "rule_based",
            "dqn_safe",
            "rule_based_fallback",
            "operator_override",
        }:
            raise HTTPException(
                status_code=409,
                detail="Recommendation algorithm is not supported for approval",
            )

        patient = (
            db.query(Patient)
            .filter(Patient.patient_id == recommendation.patient_id)
            .with_for_update()
            .populate_existing()
            .first()
        )
        encounter = (
            db.query(Encounter)
            .filter(Encounter.encounter_id == recommendation.encounter_id)
            .with_for_update()
            .populate_existing()
            .first()
        )
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        if encounter is None:
            raise HTTPException(
                status_code=409,
                detail="Recommendation Encounter no longer exists",
            )
        if encounter.patient_id != recommendation.patient_id:
            raise HTTPException(status_code=409, detail="Encounter belongs to a different patient")
        if encounter.status.upper() != "WAITING":
            raise HTTPException(status_code=409, detail="Encounter is no longer waiting for allocation")
        if patient.current_status.upper() != "WAITING":
            raise HTTPException(status_code=409, detail="Patient is not waiting for allocation")

        if recommendation.algorithm == "dqn_safe":
            if (
                recommendation.proposed_action is None
                or recommendation.final_action is None
                or recommendation.safety_overridden is None
                or recommendation.safety_original_action != recommendation.proposed_action
            ):
                raise HTTPException(
                    status_code=409,
                    detail="DQN recommendation safety metadata is incomplete",
                )

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
                raise HTTPException(
                    status_code=409,
                    detail="DQN recommendation failed current safety validation",
                )
            if not 0 <= safety_decision.final_action < len(BED_ACTIONS):
                raise HTTPException(
                    status_code=409,
                    detail="DQN recommendation does not resolve to a bed",
                )
            expected_bed_type = BED_ACTIONS[safety_decision.final_action]
            current_bed_type = db.query(Bed.bed_type).filter(
                Bed.bed_id == recommendation.recommended_bed_id
            ).scalar()
            if current_bed_type is None:
                raise HTTPException(status_code=404, detail="Recommended bed not found")
            if (
                recommendation.final_bed_type != expected_bed_type
                or current_bed_type != expected_bed_type
            ):
                raise HTTPException(
                    status_code=409,
                    detail="DQN recommendation bed no longer matches its safe action",
                )

        now = datetime.now(timezone.utc)
        admitted_encounter = approve_encounter(
            db,
            encounter.encounter_id,
            recommendation.recommended_bed_id,
            actor_id=current_user.id,
            equipment_id=request.equipment_id if legacy_operator_override else None,
            algorithm=recommendation.algorithm,
        )
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
    except LifecycleError as exc:
        db.rollback()
        _raise_lifecycle_http_error(exc)
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Approval conflicts with current resource assignments",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Allocation failed; changes were rolled back",
        ) from exc

    return {
        "patient_id": admitted_encounter.patient_id,
        "bed_id": recommendation.recommended_bed_id,
        "status": "APPROVED",
    }


@app.post("/surge/simulate", response_model=SurgeSimulationResponse)
def simulate_surge(
    request: SurgeSimulationRequest,
    current_user: User = Depends(require_permission("surge:simulate")),
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
    current_user: User = Depends(require_permission("metrics:read")),
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
        .filter(AuditLog.action.in_(("APPROVED", "ADMITTED")))
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
    current_user: User = Depends(require_permission("audit:read")),
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
