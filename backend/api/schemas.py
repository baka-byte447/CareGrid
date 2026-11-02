from pydantic import BaseModel, Field


class AllocationRecommendRequest(BaseModel):
    patient_id: str


class AllocationApproveRequest(BaseModel):
    patient_id: str
    bed_id: str


class SurgeSimulationRequest(BaseModel):
    arrival_rate_multiplier: float = Field(gt=0)
    duration_hours: int = Field(gt=0)


from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: str

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
