from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


def _strip_identity(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _validate_bcrypt_password(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes for bcrypt")
    return value


class AllocationRecommendRequest(BaseModel):
    patient_id: str
    algorithm: Optional[str] = "rule_based"


class AllocationRejectRequest(BaseModel):
    recommendation_id: int = Field(gt=0)
    patient_id: str | None = None
    reason: str = Field(min_length=3)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_rejection_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AllocationApproveRequest(BaseModel):
    recommendation_id: int = Field(gt=0)
    patient_id: str | None = None
    # Accepted only for compatibility checks; approval always uses the stored bed.
    bed_id: str | None = None


class SurgeSimulationRequest(BaseModel):
    arrival_rate_multiplier: float = Field(gt=0)
    duration_hours: int = Field(gt=0)


class RootResponse(BaseModel):
    message: str


class PatientItemResponse(BaseModel):
    patient_id: str
    age_group: str
    acuity: int
    specialty: str
    predicted_los: float
    isolation_required: bool
    ventilator_required: bool
    arrival_time: datetime
    current_status: str


class PatientsResponse(BaseModel):
    patients: list[PatientItemResponse]


class BedItemResponse(BaseModel):
    bed_id: str
    bed_type: str
    ward: str
    status: str
    isolation_capable: bool


class BedsResponse(BaseModel):
    beds: list[BedItemResponse]


class StaffItemResponse(BaseModel):
    staff_id: str
    role: str
    skill_level: str
    shift: str
    workload: int


class StaffResponse(BaseModel):
    staff: list[StaffItemResponse]


class EquipmentItemResponse(BaseModel):
    equipment_id: str
    type: str
    status: str
    location: str


class EquipmentResponse(BaseModel):
    equipment: list[EquipmentItemResponse]

class AllocationRecommendResponse(BaseModel):
    recommendation_id: int
    patient_id: str
    recommended_bed_id: str | None
    algorithm: str
    reason: str
    status: str

class SafetyBlockResponse(BaseModel):
    overridden: bool
    rule_triggered: str | None = None
    original_action: int
    reason: str | None = None


class DQNAllocationRecommendResponse(AllocationRecommendResponse):
    safety: SafetyBlockResponse
    q_values: list[float] | None = None
    los_estimate_days: float | None = None
    proposed_action: int | None = None
    final_action: int | None = None
    proposed_bed_type: str | None = None
    final_bed_type: str | None = None

class AllocationApproveResponse(BaseModel):
    patient_id: str
    bed_id: str
    status: str


class WaitingPatientsElapsedResponse(BaseModel):
    avg: float
    max: float


class ConstraintViolationsResponse(BaseModel):
    acuity_tier: int
    isolation: int
    ventilator: int
    double_booking: int
    total: int


class SurgeMetricsResponse(BaseModel):
    patients_total: int
    patients_admitted: int
    patients_discharged: int
    patients_still_waiting: int
    avg_wait_min: float
    median_wait_min: float
    avg_wait_incl_unadmitted_min: float
    p90_wait_incl_unadmitted_min: float
    p90_wait_min: float
    max_wait_min: float
    avg_wait_by_acuity_min: dict[str, float | None]
    pct_admitted_within_60min: float
    icu_utilization: float | None
    step_down_utilization: float | None
    ward_utilization: float | None
    overall_bed_utilization: float
    ventilator_utilization: float | None
    bed_turnover_per_bed_per_day: float
    peak_waiting_queue: int
    constraint_violations: ConstraintViolationsResponse
    measurement_window_hours: float
    waiting_patients_elapsed_wait_min: WaitingPatientsElapsedResponse


class SurgeSimulationResponse(BaseModel):
    status: str
    arrival_rate_multiplier: float
    duration_hours: int
    patients_arrived: int
    simulation_start: str
    simulation_end: str
    metrics: SurgeMetricsResponse


class MetricsResponse(BaseModel):
    patients_total: int
    patients_waiting: int
    patients_admitted: int
    beds_total: int
    beds_available: int
    beds_occupied: int
    bed_occupancy_rate: float
    ventilators_total: int
    ventilators_available: int
    ventilators_in_use: int
    approved_allocations: int


class AuditItemResponse(BaseModel):
    patient_id: str
    bed_id: str | None
    action: str
    algorithm: str
    timestamp: str


class AuditResponse(BaseModel):
    audit: list[AuditItemResponse]


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    _strip_username = field_validator("username", mode="before")(_strip_identity)
    _strip_email = field_validator("email", mode="before")(_strip_identity)
    _check_password_bytes = field_validator("password")(_validate_bcrypt_password)


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: str

    _strip_username = field_validator("username", mode="before")(_strip_identity)
    _strip_email = field_validator("email", mode="before")(_strip_identity)
    _check_password_bytes = field_validator("password")(_validate_bcrypt_password)


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserLogin(BaseModel):
    username: str
    password: str

    _strip_username = field_validator("username", mode="before")(_strip_identity)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool

    model_config = {"from_attributes": True}
