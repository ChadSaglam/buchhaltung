"""Audit-log response schemas (B-59)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AuditEntryOut(BaseModel):
    id: int
    action: str
    actor_user_id: int | None = None
    target_type: str | None = None
    target_id: str | None = None
    detail: dict[str, Any] | None = None
    created_at: str | None = None


class AuditListResponse(BaseModel):
    count: int
    items: list[AuditEntryOut]
