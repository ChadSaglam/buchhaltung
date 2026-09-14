from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator
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
    tenant_slug: str | None = None
    subscription_plan: str = "free"
    trial_ends_at: datetime | None = None


class SsoRequest(BaseModel):
    """`POST /api/auth/sso` — the SSO token billing put into the `/sso#token=` fragment."""

    token: str


class ProfileUpdate(BaseModel):
    """Self-service: what a user may change about themselves (B-46)."""

    display_name: str = Field(min_length=1, max_length=255)

    @field_validator("display_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Anzeigename darf nicht leer sein")
        return v


class TenantUpdate(BaseModel):
    """Tenant-wide: the company name (admin and up)."""

    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Firmenname darf nicht leer sein")
        return v
