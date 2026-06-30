from __future__ import annotations

from pydantic import BaseModel, EmailStr
from pydantic.config import ConfigDict


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str = ""
    tenant_name: str = "Meine Firma"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    role: str
    tenant_id: int
    tenant_name: str