from pydantic import BaseModel, Field


class AllocationRecommendRequest(BaseModel):
    patient_id: str


class AllocationApproveRequest(BaseModel):
    patient_id: str
    bed_id: str


class SurgeSimulationRequest(BaseModel):
    arrival_rate_multiplier: float = Field(gt=0)
    duration_hours: int = Field(gt=0)