from pydantic import BaseModel


class AllocationRecommendRequest(BaseModel):
    patient_id: str


class AllocationApproveRequest(BaseModel):
    patient_id: str
    bed_id: str


class SurgeSimulationRequest(BaseModel):
    arrival_rate_multiplier: float
    duration_hours: int