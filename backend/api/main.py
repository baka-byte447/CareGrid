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
def get_patients():
    return {
        "patients": []
    }


@app.get("/beds")
def get_beds():
    return {
        "beds": []
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