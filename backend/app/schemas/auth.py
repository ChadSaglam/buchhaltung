from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic.config import ConfigDict

#: B-55. Length is the only rule that reliably buys entropy; composition rules
#: ("one upper, one digit, one symbol") push people to `Passwort1!` and no
#: further. 12 is the NIST-style floor; the 128 cap keeps bcrypt from hashing a
#: megabyte someone pasted.
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

NewPassword = Annotated[
    str,
    Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description=f"Mindestens {MIN_PASSWORD_LENGTH} Zeichen.",
    ),
]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: NewPassword
    display_name: str = ""
    tenant_name: str = "Meine Firma"


class LoginRequest(BaseModel):
    email: EmailStr
    #: Not `NewPassword`: an account created under the old floor must still be
    #: able to sign in, and a length rule on login leaks the rule to an attacker.
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


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
