from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


def _strip_identity(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


def _validate_bcrypt_password(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 UTF-8 bytes for bcrypt")
    return value


class PatientIntakeRequest(BaseModel):
    patient_id: Optional[str] = Field(default=None, min_length=1, max_length=10)
    age_group: str = Field(min_length=1, max_length=20)
    acuity: int = Field(ge=1, le=5)
    specialty: str = Field(min_length=1, max_length=50)
    isolation_required: bool = False
    ventilator_required: bool = False
    arrival_time: Optional[datetime] = None

    _strip_patient_id = field_validator("patient_id", mode="before")(_strip_identity)
    _strip_age_group = field_validator("age_group", mode="before")(_strip_identity)
    _strip_specialty = field_validator("specialty", mode="before")(_strip_identity)


class PatientIntakeResponse(BaseModel):
    patient_id: str
    encounter_id: int
    age_group: str
    acuity: int
    specialty: str
    predicted_los: float | None
    isolation_required: bool
    ventilator_required: bool
    arrival_time: datetime
    current_status: str
    encounter_status: str


class AllocationRecommendRequest(BaseModel):
    patient_id: str
    algorithm: Optional[str] = "rule_based"


class AllocationRejectRequest(BaseModel):
    recommendation_id: Optional[int] = Field(default=None, gt=0)
    patient_id: Optional[str] = None
    reason: str = Field(min_length=3)

    _strip_patient_id = field_validator("patient_id", mode="before")(_strip_identity)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_rejection_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_recommendation_or_patient(self) -> "AllocationRejectRequest":
        if self.recommendation_id is None and not self.patient_id:
            raise ValueError("recommendation_id is required unless patient_id is provided for legacy compatibility")
        return self


class AllocationApproveRequest(BaseModel):
    recommendation_id: Optional[int] = Field(default=None, gt=0)
    patient_id: Optional[str] = None
    bed_id: Optional[str] = None
    encounter_id: Optional[int] = None
    equipment_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_approval_target(self) -> "AllocationApproveRequest":
        if self.recommendation_id is None and (not self.patient_id or not self.bed_id):
            raise ValueError("recommendation_id or both patient_id and bed_id are required")
        if self.recommendation_id is not None and self.equipment_id is not None:
            raise ValueError("equipment_id cannot be supplied with a persisted recommendation")
        return self


class DischargeRequest(BaseModel):
    release_reason: str = Field(default="discharge", min_length=1, max_length=100)
    encounter_id: Optional[int] = None

    _strip_release_reason = field_validator("release_reason", mode="before")(_strip_identity)


class DischargeResponse(BaseModel):
    patient_id: str
    encounter_id: int
    bed_id: str
    bed_status: str
    released_equipment_ids: list[str]
    patient_status: str
    encounter_status: str
    discharged_at: datetime


class TransferRequest(BaseModel):
    destination_bed_id: str = Field(min_length=1, max_length=10)
    release_reason: str = Field(default="transfer", min_length=1, max_length=100)
    encounter_id: Optional[int] = None

    _strip_destination_bed_id = field_validator("destination_bed_id", mode="before")(_strip_identity)
    _strip_release_reason = field_validator("release_reason", mode="before")(_strip_identity)


class TransferResponse(BaseModel):
    patient_id: str
    encounter_id: int
    from_bed_id: str
    to_bed_id: str
    status: str


class BedCleaningResponse(BaseModel):
    bed_id: str
    status: str


class BedCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}
    bed_id: str = Field(min_length=1, max_length=10)
    bed_type: str = Field(min_length=1, max_length=30)
    ward: str = Field(min_length=1, max_length=50)
    isolation_capable: bool = False

    _strip_bed_id = field_validator("bed_id", mode="before")(_strip_identity)
    _strip_bed_type = field_validator("bed_type", mode="before")(_strip_identity)
    _strip_ward = field_validator("ward", mode="before")(_strip_identity)


class BedCreateResponse(BaseModel):
    message: str
    bed: "BedItemResponse"


class BedReleaseResponse(BaseModel):
    message: str
    bed: BedCleaningResponse


class EquipmentAssignRequest(BaseModel):
    patient_id: Optional[str] = None
    encounter_id: Optional[int] = None

    _strip_patient_id = field_validator("patient_id", mode="before")(_strip_identity)

    @model_validator(mode="after")
    def _require_target(self) -> "EquipmentAssignRequest":
        if not self.patient_id and self.encounter_id is None:
            raise ValueError("Either patient_id or encounter_id must be provided")
        return self


class EquipmentReleaseRequest(BaseModel):
    patient_id: Optional[str] = None
    encounter_id: Optional[int] = None
    release_reason: str = Field(default="released", min_length=1, max_length=100)

    _strip_patient_id = field_validator("patient_id", mode="before")(_strip_identity)
    _strip_release_reason = field_validator("release_reason", mode="before")(_strip_identity)


class EquipmentAssignmentResponse(BaseModel):
    assignment_id: int
    encounter_id: int
    patient_id: str
    equipment_id: str
    status: str
    assigned_at: datetime
    released_at: Optional[datetime] = None
    release_reason: Optional[str] = None


class SurgeSimulationRequest(BaseModel):
    adaptive: bool = False
    arrival_rate_multiplier: float = Field(gt=0)
    duration_hours: int = Field(gt=0)


class RootResponse(BaseModel):
    message: str


class PatientItemResponse(BaseModel):
    patient_id: str
    age_group: str
    acuity: int
    specialty: str
    predicted_los: float | None
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


class BedListItemResponse(BedItemResponse):
    patient_id: str | None
    predicted_los: float | None


class BedsResponse(BaseModel):
    beds: list[BedListItemResponse]


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

from rl.serving.explainability import ClinicalExplanation


class AllocationRecommendResponse(BaseModel):
    explanation: ClinicalExplanation | None = None
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


class SimulatedOperations(BaseModel):
    macro_interrupts: int
    fatigue: float
    overtime_minutes: float
    transfer_requests: int


class SurgeSimulationResponse(BaseModel):
    operations: SimulatedOperations | None = None
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
    patient_id: str | None
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
