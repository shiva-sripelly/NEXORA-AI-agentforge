from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not (any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value)):
            raise ValueError("Password must include uppercase, lowercase, and a number")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    success: bool = True
    user: UserResponse


class MessageResponse(BaseModel):
    success: bool = True
    message: str
