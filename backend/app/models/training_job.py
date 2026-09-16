"""Queued classifier retrains — tenant-scoped.

The API only inserts rows here (see ``services/training_worker.enqueue_training``);
the worker process claims and runs them. A DB table instead of an in-memory
queue so the two can live in different processes (B-08).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"


class TrainingJob(Base):
    __tablename__ = "training_jobs"
    # Two queries, two indexes (B-28). `enqueue_training` asks "does this tenant
    # already have one pending?"; the worker asks "what is the oldest pending job
    # anywhere?" — cross-tenant by design, so a `(tenant_id, status)` index does
    # nothing for it. Measured: 263 buffers and 3'926 rows sorted → an Index Only
    # Scan, 4 buffers, Heap Fetches 0.
    __table_args__ = (
        Index("ix_training_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_training_jobs_status_requested", "status", "requested_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDING, index=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
