from typing import Optional
from pydantic import BaseModel, Field

try:
    import email_validator
    from pydantic import EmailStr
except ImportError:
    EmailStr = str

class AllocationRecommendRequest(BaseModel):
    patient_id: str
    algorithm: Optional[str] = "rule_based"


class AllocationRejectRequest(BaseModel):
    patient_id: str
    reason: str = Field(min_length=3)


class AllocationApproveRequest(BaseModel):
    patient_id: str
    bed_id: str


class SurgeSimulationRequest(BaseModel):
    arrival_rate_multiplier: float = Field(gt=0)
    duration_hours: int = Field(gt=0)





class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: str

class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserLogin(BaseModel):
    username: str
    password: str


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
