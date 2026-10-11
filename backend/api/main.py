from fastapi import Depends
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.models import Patient, Bed, Staff, Equipment

from fastapi import FastAPI
from backend.api.schemas import (
    AllocationRecommendRequest,
    AllocationApproveRequest,
    SurgeSimulationRequest,
)

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
def recommend_allocation(request: AllocationRecommendRequest):
    return {
        "patient_id": request.patient_id,
        "status": "NOT_IMPLEMENTED"
    }


@app.post("/allocation/approve")
def approve_allocation(request: AllocationApproveRequest):
    return {
        "patient_id": request.patient_id,
        "bed_id": request.bed_id,
        "status": "NOT_IMPLEMENTED"
    }


@app.post("/surge/simulate")
def simulate_surge(request: SurgeSimulationRequest):
    return {
        "arrival_rate_multiplier": request.arrival_rate_multiplier,
        "duration_hours": request.duration_hours,
        "status": "NOT_IMPLEMENTED"
    }


@app.get("/metrics")
def get_metrics():
    return {
        "status": "NOT_IMPLEMENTED"
    }


@app.get("/audit")
def get_audit():
    return {
        "audit": []
    }