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
