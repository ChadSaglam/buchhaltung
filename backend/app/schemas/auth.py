"""Auth request/response schemas."""
from pydantic import BaseModel, EmailStr


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
    id: int
    email: str
    display_name: str
    role: str
    tenant_id: int
    tenant_name: str

    class Config:
        from_attributes = True
